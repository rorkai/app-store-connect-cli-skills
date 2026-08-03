#!/usr/bin/env python3
"""Build deterministic, privacy-aware evidence from ASC analytics reports.

Requires Python 3.10 or newer. This module deliberately performs no
authentication or network access. It
consumes the JSON inventory produced by ``asc analytics view
--include-segments`` and report files that have already been downloaded.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "1.0"
DECIMAL_CONTEXT = Context(prec=80, rounding=ROUND_HALF_EVEN)
SUPPORTED_GRANULARITIES = frozenset({"DAILY", "WEEKLY", "MONTHLY"})
SUPPORTED_PRIVACY_MODES = frozenset({"confidential", "redacted"})
OUTPUT_FILENAMES = {
    "facts": "facts.json",
    "evidence_manifest": "evidence-manifest.json",
    "gaps": "gaps.json",
}
SEGMENT_SUFFIXES = (
    "",
    ".txt",
    ".tsv",
    ".csv",
    ".gz",
    ".txt.gz",
    ".tsv.gz",
    ".csv.gz",
)


class EvidenceError(ValueError):
    """Raised when input cannot be used without risking a misleading result."""


def _normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\ufeff", " ").replace("\xa0", " ")
    text = re.sub(r"[^0-9A-Za-z]+", " ", text)
    return " ".join(text.casefold().split())


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise EvidenceError("a numeric metric is not finite")
    if value == 0:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _parse_iso_date(value: object, label: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError(f"{label} must be an ISO date in YYYY-MM-DD format")
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError as exc:
        raise EvidenceError(
            f"{label} must be an ISO date in YYYY-MM-DD format"
        ) from exc
    if parsed.isoformat() != value.strip():
        raise EvidenceError(f"{label} must be an ISO date in YYYY-MM-DD format")
    return parsed


def _parse_decimal(value: str, *, integral: bool, label: str) -> Decimal:
    text = value.strip()
    if not text:
        raise EvidenceError(f"{label} contains an empty numeric value")
    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise EvidenceError(f"{label} contains an invalid numeric value") from exc
    if not parsed.is_finite():
        raise EvidenceError(f"{label} contains a non-finite numeric value")
    if integral and parsed != parsed.to_integral_value(context=DECIMAL_CONTEXT):
        raise EvidenceError(f"{label} must contain whole-number values")
    return parsed


def _decimal_add(left: Decimal, right: Decimal) -> Decimal:
    return DECIMAL_CONTEXT.add(left, right)


def _decimal_subtract(left: Decimal, right: Decimal) -> Decimal:
    return DECIMAL_CONTEXT.subtract(left, right)


def _decimal_percent_change(change: Decimal, previous: Decimal) -> Decimal:
    ratio = DECIMAL_CONTEXT.divide(change, previous.copy_abs())
    return DECIMAL_CONTEXT.multiply(ratio, Decimal(100))


def _parse_size(value: object) -> int:
    if isinstance(value, bool):
        raise EvidenceError("segment size metadata is invalid")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        raise EvidenceError("segment size metadata is invalid")
    if parsed < 0:
        raise EvidenceError("segment size metadata is invalid")
    return parsed


def _parse_checksum(value: object) -> str:
    if not isinstance(value, str):
        raise EvidenceError("segment checksum metadata is missing or invalid")
    checksum = value.strip().casefold()
    if checksum.startswith("md5:") or checksum.startswith("md5="):
        checksum = checksum[4:].strip()
    if not re.fullmatch(r"[0-9a-f]{32}", checksum):
        raise EvidenceError("segment checksum metadata is not an MD5 hex digest")
    return checksum


def _period_end(start: date, granularity: str) -> date:
    if granularity == "DAILY":
        return start
    if granularity == "WEEKLY":
        return start + timedelta(days=6)
    if granularity == "MONTHLY":
        if start.month == 12:
            next_month = date(start.year + 1, 1, 1)
        else:
            next_month = date(start.year, start.month + 1, 1)
        return next_month - timedelta(days=1)
    raise EvidenceError("unsupported granularity")


@dataclass(frozen=True)
class GroupMetric:
    dimension_headers: tuple[str, ...]
    count_headers: tuple[str, ...]
    values: Mapping[str, tuple[str, str]]
    dimension_key: str


@dataclass(frozen=True)
class NamedMetric:
    metric: str
    headers: tuple[str, ...]
    unit: str
    integral: bool = True
    generic_currency: bool = False


@dataclass(frozen=True)
class ReportSpec:
    key: str
    display_name: str
    aliases: tuple[str, ...]
    date_headers: tuple[str, ...]
    daily_lag_days: int
    named_metrics: tuple[NamedMetric, ...] = ()
    grouped_metric: GroupMetric | None = None
    non_additive_headers: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    caveats: tuple[str, ...] = ()


DOWNLOAD_TYPES: Mapping[str, tuple[str, str]] = {
    "first time download": ("first_time_downloads", "First-time download"),
    "redownload": ("redownloads", "Redownload"),
    "manual update": ("updates", "Update"),
    "auto update": ("updates", "Update"),
    "automatic update": ("updates", "Update"),
    "update": ("updates", "Update"),
    "restore": ("restores", "Restore"),
}

DISCOVERY_EVENTS: Mapping[str, tuple[str, str]] = {
    "impression": ("impressions", "Impression"),
    "impressions": ("impressions", "Impression"),
    "page view": ("page_views", "Page view"),
    "page views": ("page_views", "Page view"),
    "tap": ("taps", "Tap"),
    "taps": ("taps", "Tap"),
}

INSTALL_EVENTS: Mapping[str, tuple[str, str]] = {
    "install": ("installs", "Install"),
    "installation": ("installs", "Install"),
    "delete": ("deletions", "Delete"),
    "deletion": ("deletions", "Delete"),
}

SUBSCRIPTION_STATES = (
    "active plans all",
    "subscription offers all",
    "free trials",
    "paid offers",
    "paid plans all",
    "full price",
    "preserved price",
    "contingent price",
    "grace period",
    "billing issue all",
    "billing retry",
    "suspended",
    "churned all",
    "voluntarily churned",
    "involuntarily churned",
)
SUBSCRIPTION_STATE_VALUES: Mapping[str, tuple[str, str]] = {
    value: (value.replace(" ", "_"), value.title())
    for value in SUBSCRIPTION_STATES
}

SUBSCRIPTION_EVENT_SUBTYPES = (
    "free trial starts",
    "paid offer starts",
    "free trial renewals",
    "paid offer renewals",
    "full price from free trial",
    "contingent price from free trial",
    "full price from paid offer",
    "contingent price from paid offer",
    "full price subscription starts",
    "contingent price subscription starts",
    "full price renewals",
    "preserved price renewals",
    "contingent price renewals",
    "contingent price renewal from full price",
    "contingent price renewal from preserved price",
    "full price renewal from contingent price",
    "preserved price renewal from contingent price",
    "preserved price renewal from full price",
    "full price renewal from preserved price",
    "full price commitment based payments",
    "contingent price commitment based payments",
    "preserved price commitment based payments",
    "entered grace period from full price",
    "entered grace period from contingent price",
    "entered grace period from preserved price",
    "entered grace period from free trial",
    "entered grace period from paid offer",
    "entered billing retry from full price",
    "entered billing retry from contingent price",
    "entered billing retry from preserved price",
    "entered billing retry from free trial",
    "entered billing retry from paid offer",
    "entered billing retry from grace period",
    "full price recoveries from grace period",
    "contingent price recoveries from grace period",
    "preserved price recoveries from grace period",
    "paid offer recoveries from grace period",
    "free trial recoveries from grace period",
    "full price recoveries from billing retry",
    "contingent price recoveries from billing retry",
    "preserved price recoveries from billing retry",
    "paid offer recoveries from billing retry",
    "free trial recoveries from billing retry",
    "involuntary churn from free trials",
    "involuntary churn from paid offers",
    "involuntary churn from full price",
    "involuntary churn from contingent price",
    "involuntary churn from preserved price",
    "voluntary churn from free trials",
    "voluntary churn from paid offers",
    "voluntary churn from full price",
    "voluntary churn from contingent price",
    "voluntary churn from preserved price",
    "refunds from paid offers",
    "refunds from full price",
    "refunds from contingent price",
    "refunds from preserved price",
    "plan changes",
    "offer to offer",
    "offers from paid",
    "free trial extensions",
    "paid offer extensions",
    "contingent price extensions",
    "preserved price extensions",
)
SUBSCRIPTION_EVENT_VALUES: Mapping[str, tuple[str, str]] = {
    value: (value.replace(" ", "_"), value.title())
    for value in SUBSCRIPTION_EVENT_SUBTYPES
}

CORRECTION_CAVEAT = (
    "Apple may replace report data in a later processing snapshot."
)
PRIVACY_CAVEAT = (
    "Apple may apply privacy thresholds or statistical noise; treat small "
    "changes cautiously."
)
OPT_IN_CAVEAT = (
    "This usage metric represents users who opted in to share analytics and "
    "must not be presented as the full user population."
)

REPORT_SPECS: tuple[ReportSpec, ...] = (
    ReportSpec(
        key="app_store_downloads",
        display_name="App Store Downloads",
        aliases=("app store downloads", "app downloads", "downloads"),
        date_headers=("date",),
        daily_lag_days=2,
        grouped_metric=GroupMetric(
            dimension_headers=("download type",),
            count_headers=("counts", "count"),
            values=DOWNLOAD_TYPES,
            dimension_key="downloadType",
        ),
        non_additive_headers={"unique_devices": ("unique devices",)},
        caveats=(
            CORRECTION_CAVEAT,
            "Download events are not a count of unique people.",
            PRIVACY_CAVEAT,
        ),
    ),
    ReportSpec(
        key="app_store_discovery_and_engagement",
        display_name="App Store Discovery and Engagement",
        aliases=("app store discovery and engagement", "discovery and engagement"),
        date_headers=("date",),
        daily_lag_days=3,
        grouped_metric=GroupMetric(
            dimension_headers=("event",),
            count_headers=("counts", "count"),
            values=DISCOVERY_EVENTS,
            dimension_key="event",
        ),
        non_additive_headers={
            "unique_counts": ("unique counts",),
            "unique_devices": ("unique devices",),
        },
        caveats=(CORRECTION_CAVEAT, PRIVACY_CAVEAT),
    ),
    ReportSpec(
        key="app_store_purchases",
        display_name="App Store Purchases",
        aliases=("app store purchases", "app purchases", "purchases"),
        date_headers=("date",),
        daily_lag_days=2,
        named_metrics=(
            NamedMetric("purchases", ("purchases",), "count"),
            NamedMetric("proceeds", ("proceeds in usd",), "USD", integral=False),
            NamedMetric("sales", ("sales in usd",), "USD", integral=False),
            NamedMetric(
                "proceeds", ("proceeds",), "currency", integral=False, generic_currency=True
            ),
            NamedMetric(
                "sales", ("sales",), "currency", integral=False, generic_currency=True
            ),
        ),
        non_additive_headers={"paying_users": ("paying users",)},
        caveats=(
            CORRECTION_CAVEAT,
            "Sales and proceeds are Apple estimates, not settled financial statements.",
        ),
    ),
    ReportSpec(
        key="app_sessions",
        display_name="App Sessions",
        aliases=("app sessions", "sessions"),
        date_headers=("date",),
        daily_lag_days=5,
        named_metrics=(
            NamedMetric("sessions", ("sessions",), "count"),
            NamedMetric(
                "total_session_duration_seconds",
                ("total session duration",),
                "seconds",
            ),
        ),
        non_additive_headers={"unique_devices": ("unique devices",)},
        caveats=(CORRECTION_CAVEAT, OPT_IN_CAVEAT, PRIVACY_CAVEAT),
    ),
    ReportSpec(
        key="app_store_installations_and_deletions",
        display_name="App Store Installations and Deletions",
        aliases=(
            "app store installations and deletions",
            "app installations and deletions",
            "app installs",
            "installations and deletions",
        ),
        date_headers=("date",),
        daily_lag_days=5,
        grouped_metric=GroupMetric(
            dimension_headers=("event",),
            count_headers=("counts", "count"),
            values=INSTALL_EVENTS,
            dimension_key="event",
        ),
        non_additive_headers={"unique_devices": ("unique devices",)},
        caveats=(CORRECTION_CAVEAT, OPT_IN_CAVEAT, PRIVACY_CAVEAT),
    ),
    ReportSpec(
        key="app_crashes",
        display_name="App Crashes",
        aliases=("app crashes", "crashes"),
        date_headers=("date",),
        daily_lag_days=5,
        named_metrics=(NamedMetric("crashes", ("crashes",), "count"),),
        non_additive_headers={"unique_devices": ("unique devices",)},
        caveats=(CORRECTION_CAVEAT, OPT_IN_CAVEAT, PRIVACY_CAVEAT),
    ),
    ReportSpec(
        key="app_store_subscription_state",
        display_name="App Store Subscription State",
        aliases=("app store subscription state", "subscription state"),
        date_headers=("date",),
        daily_lag_days=3,
        grouped_metric=GroupMetric(
            dimension_headers=("state metric",),
            count_headers=("counts", "count"),
            values=SUBSCRIPTION_STATE_VALUES,
            dimension_key="stateMetric",
        ),
        caveats=(
            CORRECTION_CAVEAT,
            "Subscription state is a point-in-time snapshot and must not be summed across dates.",
            PRIVACY_CAVEAT,
        ),
    ),
    ReportSpec(
        key="app_store_subscription_event",
        display_name="App Store Subscription Event",
        aliases=("app store subscription event", "subscription event"),
        date_headers=("event date", "date"),
        daily_lag_days=3,
        grouped_metric=GroupMetric(
            dimension_headers=("event sub type",),
            count_headers=("counts", "count"),
            values=SUBSCRIPTION_EVENT_VALUES,
            dimension_key="eventSubType",
        ),
        caveats=(CORRECTION_CAVEAT, PRIVACY_CAVEAT),
    ),
)

REPORT_BY_KEY = {spec.key: spec for spec in REPORT_SPECS}


@dataclass
class GapDraft:
    code: str
    severity: str
    message: str
    report: str | None = None
    metric: str | None = None
    period: Mapping[str, str] | None = None
    evidence_keys: set[tuple[int, int, int]] = field(default_factory=set)


@dataclass
class EvidenceDraft:
    key: tuple[int, int, int]
    report: str
    report_date: str | None
    processing_date: str
    granularity: str
    size: int
    checksum: str
    row_count: int
    compression: str
    delimiter: str
    report_id: str | None
    instance_id: str | None
    version: str | None
    segment_id: str


@dataclass(frozen=True)
class RecognizedSchema:
    signature: tuple[object, ...]
    required_headers: tuple[str, ...]


@dataclass
class ParsedRow:
    report: str
    processing_date: date
    data_date: date
    values: Mapping[str, str]
    evidence_key: tuple[int, int, int]


@dataclass
class Bucket:
    report: str
    metric: str
    unit: str
    dimensions: Mapping[str, str]
    data_date: date
    processing_date: date
    value: Decimal = Decimal(0)
    evidence_keys: set[tuple[int, int, int]] = field(default_factory=set)
    caveats: set[str] = field(default_factory=set)


def _classify_report(report: Mapping[str, object]) -> ReportSpec | None:
    name = _normalize_text(report.get("name"))
    without_suffix = re.sub(r"\b(?:standard|summary|detailed|detail|report)\b", " ", name)
    without_suffix = " ".join(without_suffix.split())
    for spec in REPORT_SPECS:
        for alias in spec.aliases:
            if name == alias or without_suffix == alias:
                return spec
            if name.startswith(f"{alias} ") and any(
                marker in name.split() for marker in ("standard", "summary", "detailed", "detail")
            ):
                return spec
    return None


def _is_standard_report(report: Mapping[str, object], spec: ReportSpec) -> bool:
    report_type = _normalize_text(report.get("reportType"))
    if report_type in {"standard", "summary"}:
        return True
    if not report_type:
        name = _normalize_text(report.get("name"))
        if " standard" in f" {name}" or " summary" in f" {name}":
            return True
        return spec.key == "app_crashes" and name == "app crashes"
    return False


def _safe_opaque_id(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if not re.fullmatch(r"[A-Za-z0-9._:-]+", value):
        return None
    return value


def _safe_segment_id(value: object) -> str:
    segment_id = _safe_opaque_id(value)
    if segment_id is None or segment_id in {".", ".."}:
        raise EvidenceError("a selected segment has a missing or unsafe identifier")
    return segment_id


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _candidate_files(segments_dir: Path) -> list[Path]:
    excluded = set(OUTPUT_FILENAMES.values())
    return sorted(
        (
            path
            for path in segments_dir.rglob("*")
            if path.is_file() and not path.name.startswith(".") and path.name not in excluded
        ),
        key=lambda path: path.relative_to(segments_dir).as_posix(),
    )


def _resolve_segment_file(
    segment: Mapping[str, object],
    *,
    segments_dir: Path,
    files: Sequence[Path],
    selected_segment_count: int,
    ordinal: int,
) -> Path:
    root = segments_dir.resolve()
    local_path = segment.get("localPath")
    if local_path is not None:
        if not isinstance(local_path, str) or not local_path.strip():
            raise EvidenceError(f"selected segment #{ordinal} has an invalid localPath")
        candidate = Path(local_path)
        candidate = candidate if candidate.is_absolute() else segments_dir / candidate
        resolved = candidate.resolve()
        if not _path_within(resolved, root) or not resolved.is_file():
            raise EvidenceError(f"selected segment #{ordinal} localPath is unavailable")
        return resolved

    segment_id = _safe_segment_id(segment.get("id"))
    accepted_names = {f"{segment_id}{suffix}" for suffix in SEGMENT_SUFFIXES}
    matches = [path.resolve() for path in files if path.name in accepted_names]
    if len(matches) > 1:
        raise EvidenceError(f"selected segment #{ordinal} maps to multiple local files")
    if matches:
        resolved = matches[0]
        if not _path_within(resolved, root):
            raise EvidenceError(f"selected segment #{ordinal} resolves outside segments-dir")
        return resolved
    if selected_segment_count == 1 and len(files) == 1:
        resolved = files[0].resolve()
        if not _path_within(resolved, root):
            raise EvidenceError("the only local segment file resolves outside segments-dir")
        return resolved
    raise EvidenceError(f"selected segment #{ordinal} has no exact local file match")


def _verify_segment(path: Path, segment: Mapping[str, object], ordinal: int) -> tuple[int, str]:
    expected_size = _parse_size(segment.get("sizeInBytes"))
    expected_checksum = _parse_checksum(segment.get("checksum"))
    try:
        digest = hashlib.md5(usedforsecurity=False)
    except TypeError:  # pragma: no cover - for older Python/OpenSSL builds
        digest = hashlib.md5()
    actual_size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            actual_size += len(chunk)
            digest.update(chunk)
    if actual_size != expected_size:
        raise EvidenceError(f"selected segment #{ordinal} failed its byte-size check")
    if digest.hexdigest().casefold() != expected_checksum:
        raise EvidenceError(f"selected segment #{ordinal} failed its MD5 check")
    return actual_size, expected_checksum


def _parse_segment(path: Path) -> tuple[list[dict[str, str]], str, str, set[str]]:
    with path.open("rb") as raw:
        magic = raw.read(2)
        raw.seek(0)
        compression = "gzip" if magic == b"\x1f\x8b" else "none"
        binary: Any = gzip.GzipFile(fileobj=raw, mode="rb") if compression == "gzip" else raw
        text = io.TextIOWrapper(binary, encoding="utf-8-sig", newline="")
        try:
            header_line = text.readline()
            if not header_line:
                raise EvidenceError("a selected segment is empty")
            if "\t" in header_line:
                delimiter_character = "\t"
                delimiter_name = "tab"
            elif "," in header_line:
                delimiter_character = ","
                delimiter_name = "comma"
            else:
                raise EvidenceError("a selected segment header is neither tab nor comma delimited")

            header_values = next(csv.reader([header_line], delimiter=delimiter_character))
            normalized_headers = [_normalize_text(header) for header in header_values]
            if not all(normalized_headers):
                raise EvidenceError("a selected segment contains a blank header")
            if len(set(normalized_headers)) != len(normalized_headers):
                raise EvidenceError("a selected segment contains duplicate normalized headers")

            rows: list[dict[str, str]] = []
            reader = csv.reader(text, delimiter=delimiter_character)
            for values in reader:
                if not values or not any(value.strip() for value in values):
                    continue
                if len(values) != len(normalized_headers):
                    raise EvidenceError("a selected segment row does not match its header")
                rows.append(
                    {
                        header: value.strip()
                        for header, value in zip(normalized_headers, values, strict=True)
                    }
                )
        except (csv.Error, EOFError, OSError, UnicodeError) as exc:
            raise EvidenceError("a selected segment could not be decoded safely") from exc
        finally:
            text.detach()
    return rows, compression, delimiter_name, set(normalized_headers)


def _first_header(headers: Iterable[str], candidates: Sequence[str]) -> str | None:
    available = set(headers)
    return next((candidate for candidate in candidates if candidate in available), None)


def _recognized_schema(spec: ReportSpec, headers: set[str]) -> RecognizedSchema:
    date_header = _first_header(headers, spec.date_headers)
    if date_header is None:
        raise EvidenceError("a supported report segment is missing its report data date")

    if spec.grouped_metric is not None:
        grouped = spec.grouped_metric
        dimension_header = _first_header(headers, grouped.dimension_headers)
        count_header = _first_header(headers, grouped.count_headers)
        if dimension_header is None or count_header is None:
            raise EvidenceError(
                "a grouped report segment is missing its required dimension or count"
            )
        required = [date_header, dimension_header, count_header]
        return RecognizedSchema(
            signature=(
                "grouped",
                date_header,
                dimension_header,
                count_header,
            ),
            required_headers=tuple(required),
        )

    recognized: dict[str, tuple[str, bool, str]] = {}
    for named in spec.named_metrics:
        matches = [header for header in named.headers if header in headers]
        if len(matches) > 1:
            raise EvidenceError("a named report has an ambiguous recognized schema")
        if not matches:
            continue
        entry = (matches[0], named.generic_currency, named.unit)
        if named.metric in recognized:
            raise EvidenceError(
                "a named report contains overlapping supported metric columns"
            )
        recognized[named.metric] = entry
    if not recognized:
        raise EvidenceError("a named report segment has no supported additive metric")

    currency_required = any(entry[1] for entry in recognized.values())
    if currency_required and "currency" not in headers:
        raise EvidenceError(
            "a generic monetary report segment is missing its currency column"
        )
    required = [date_header]
    required.extend(entry[0] for _, entry in sorted(recognized.items()))
    if currency_required:
        required.append("currency")
    return RecognizedSchema(
        signature=(
            "named",
            date_header,
            tuple(sorted(recognized.items())),
            currency_required,
        ),
        required_headers=tuple(required),
    )


def _complete_period(
    data_date: date,
    *,
    spec: ReportSpec,
    granularity: str,
    as_of: date,
    processing_date: date,
) -> bool:
    effective_as_of = min(as_of, processing_date)
    if granularity == "DAILY":
        return data_date <= effective_as_of - timedelta(days=spec.daily_lag_days)
    return _period_end(data_date, granularity) <= effective_as_of


def _period_mapping(start: date, granularity: str) -> dict[str, str]:
    return {"start": start.isoformat(), "end": _period_end(start, granularity).isoformat()}


def _previous_period_start(current: date, granularity: str) -> date:
    if granularity == "DAILY":
        return current - timedelta(days=1)
    if granularity == "WEEKLY":
        return current - timedelta(days=7)
    if granularity == "MONTHLY":
        if current.month == 1:
            return date(current.year - 1, 12, 1)
        return date(current.year, current.month - 1, 1)
    raise EvidenceError("unsupported granularity")


def _add_gap(gaps: list[GapDraft], gap: GapDraft) -> None:
    signature = (
        gap.code,
        gap.severity,
        gap.message,
        gap.report,
        gap.metric,
        json.dumps(gap.period, sort_keys=True) if gap.period else "",
        tuple(sorted(gap.evidence_keys)),
    )
    for existing in gaps:
        existing_signature = (
            existing.code,
            existing.severity,
            existing.message,
            existing.report,
            existing.metric,
            json.dumps(existing.period, sort_keys=True) if existing.period else "",
            tuple(sorted(existing.evidence_keys)),
        )
        if signature == existing_signature:
            return
    gaps.append(gap)


def _load_inventory(path: Path) -> Mapping[str, object]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("inventory is not readable JSON") from exc
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        raise EvidenceError("inventory must contain a data array")
    return value


def _select_reports_and_instances(
    inventory: Mapping[str, object],
    *,
    granularity: str,
    as_of: date,
    gaps: list[GapDraft],
) -> tuple[
    list[
        tuple[
            int,
            Mapping[str, object],
            ReportSpec,
            list[tuple[int, Mapping[str, object]]],
        ]
    ],
    set[str],
]:
    selected: list[
        tuple[int, Mapping[str, object], ReportSpec, list[tuple[int, Mapping[str, object]]]]
    ] = []
    found_supported: set[str] = set()
    for report_index, raw_report in enumerate(inventory["data"]):
        if not isinstance(raw_report, dict):
            raise EvidenceError("inventory data entries must be objects")
        report: Mapping[str, object] = raw_report
        spec = _classify_report(report)
        if spec is None:
            _add_gap(
                gaps,
                GapDraft(
                    code="unsupported_report",
                    severity="info",
                    message="An analytics report is outside the v1 evidence contract.",
                ),
            )
            continue
        found_supported.add(spec.key)
        if not _is_standard_report(report, spec):
            _add_gap(
                gaps,
                GapDraft(
                    code="unsupported_report_variant",
                    severity="warning",
                    report=spec.key,
                    message="Only Standard or Summary report variants are supported in v1.",
                ),
            )
            continue

        raw_instances = report.get("instances")
        if raw_instances is None:
            raw_instances = []
        if not isinstance(raw_instances, list):
            raise EvidenceError("report instances must be an array")
        selected_instances: list[tuple[int, Mapping[str, object]]] = []
        for instance_index, raw_instance in enumerate(raw_instances):
            if not isinstance(raw_instance, dict):
                raise EvidenceError("report instance entries must be objects")
            instance: Mapping[str, object] = raw_instance
            raw_segments = instance.get("segments")
            if raw_segments is None:
                raw_segments = []
            if not isinstance(raw_segments, list):
                raise EvidenceError("report instance segments must be an array")
            if not raw_segments:
                continue
            instance_granularity = str(
                instance.get("granularity") or report.get("granularity") or ""
            ).upper()
            if instance_granularity not in SUPPORTED_GRANULARITIES:
                raise EvidenceError("a data-bearing instance has no supported granularity")
            if instance_granularity != granularity:
                raise EvidenceError(
                    "inventory contains data-bearing instances with mixed requested granularities"
                )
            processing_date = _parse_iso_date(
                instance.get("processingDate"), "instance processingDate"
            )
            if processing_date > as_of:
                _add_gap(
                    gaps,
                    GapDraft(
                        code="future_processing_snapshot",
                        severity="info",
                        report=spec.key,
                        message=(
                            "A processing snapshot after the requested as-of date "
                            "was excluded."
                        ),
                    ),
                )
                continue
            selected_instances.append((instance_index, instance))
        if selected_instances:
            selected.append((report_index, report, spec, selected_instances))
        else:
            _add_gap(
                gaps,
                GapDraft(
                    code="no_segments",
                    severity="warning",
                    report=spec.key,
                    message="No eligible downloaded segments were available for this report.",
                ),
            )

    for spec in REPORT_SPECS:
        if spec.key not in found_supported:
            _add_gap(
                gaps,
                GapDraft(
                    code="missing_supported_report",
                    severity="info",
                    report=spec.key,
                    message="This supported Standard report was not present in the inventory.",
                ),
            )
    return selected, found_supported


def _collect_rows(
    selected: Sequence[
        tuple[int, Mapping[str, object], ReportSpec, list[tuple[int, Mapping[str, object]]]]
    ],
    *,
    segments_dir: Path,
    granularity: str,
    gaps: list[GapDraft],
) -> tuple[list[ParsedRow], list[EvidenceDraft], Mapping[str, set[str]]]:
    files = _candidate_files(segments_dir)
    segment_records: list[
        tuple[
            int,
            Mapping[str, object],
            ReportSpec,
            Mapping[str, object],
            int,
            Mapping[str, object],
        ]
    ] = []
    for report_index, report, spec, instances in selected:
        for instance_index, instance in instances:
            segments = instance.get("segments")
            assert isinstance(segments, list)
            for segment_index, raw_segment in enumerate(segments):
                if not isinstance(raw_segment, dict):
                    raise EvidenceError("segment entries must be objects")
                segment_records.append(
                    (report_index, report, spec, instance, instance_index, raw_segment)
                )

    rows: list[ParsedRow] = []
    evidence: list[EvidenceDraft] = []
    report_headers: dict[str, set[str]] = defaultdict(set)
    report_schemas: dict[str, tuple[object, ...]] = {}
    app_identifiers: set[str] = set()
    claimed_files: set[Path] = set()
    for ordinal, record in enumerate(segment_records, start=1):
        report_index, report, spec, instance, instance_index, segment = record
        segment_id = _safe_segment_id(segment.get("id"))
        path = _resolve_segment_file(
            segment,
            segments_dir=segments_dir,
            files=files,
            selected_segment_count=len(segment_records),
            ordinal=ordinal,
        )
        if path in claimed_files:
            raise EvidenceError("multiple selected segments map to the same local file")
        claimed_files.add(path)
        size, checksum = _verify_segment(path, segment, ordinal)
        parsed_rows, compression, delimiter, headers = _parse_segment(path)
        report_headers[spec.key].update(headers)
        schema = _recognized_schema(spec, headers)
        prior_schema = report_schemas.get(spec.key)
        if prior_schema is not None and prior_schema != schema.signature:
            raise EvidenceError(
                "selected segments for a report have inconsistent recognized schemas"
            )
        report_schemas[spec.key] = schema.signature
        date_header = str(schema.signature[1])
        processing_date = _parse_iso_date(
            instance.get("processingDate"), "instance processingDate"
        )
        evidence_key = (report_index, instance_index, ordinal)
        for row in parsed_rows:
            if any(not row.get(header, "").strip() for header in schema.required_headers):
                raise EvidenceError(
                    "a supported report row has a blank required metric or dimension"
                )
            app_identifier = row.get("app apple identifier", "").strip()
            if app_identifier:
                app_identifiers.add(app_identifier)
            data_date = _parse_iso_date(row.get(date_header), "report data date")
            if granularity == "WEEKLY" and data_date.weekday() != 0:
                raise EvidenceError("weekly report data dates must be Mondays")
            if granularity == "MONTHLY" and data_date.day != 1:
                raise EvidenceError("monthly report data dates must be the first day")
            rows.append(
                ParsedRow(
                    report=spec.key,
                    processing_date=processing_date,
                    data_date=data_date,
                    values=row,
                    evidence_key=evidence_key,
                )
            )
        report_date: str | None = None
        if instance.get("reportDate") is not None:
            report_date = _parse_iso_date(
                instance.get("reportDate"), "instance reportDate"
            ).isoformat()
        evidence.append(
            EvidenceDraft(
                key=evidence_key,
                report=spec.key,
                report_date=report_date,
                processing_date=processing_date.isoformat(),
                granularity=granularity,
                size=size,
                checksum=checksum,
                row_count=len(parsed_rows),
                compression=compression,
                delimiter=delimiter,
                report_id=_safe_opaque_id(report.get("id")),
                instance_id=_safe_opaque_id(instance.get("id")),
                version=_safe_opaque_id(instance.get("version")),
                segment_id=segment_id,
            )
        )
    if len(app_identifiers) > 1:
        raise EvidenceError("selected report segments contain more than one app identifier")
    return rows, evidence, report_headers


def _select_newest_partitions(
    rows: Sequence[ParsedRow], as_of: date
) -> tuple[list[ParsedRow], Mapping[tuple[str, date], int]]:
    eligible = [row for row in rows if row.data_date <= as_of]
    newest: dict[tuple[str, date], date] = {}
    snapshots: dict[tuple[str, date], set[date]] = defaultdict(set)
    for row in eligible:
        key = (row.report, row.data_date)
        snapshots[key].add(row.processing_date)
        if key not in newest or row.processing_date > newest[key]:
            newest[key] = row.processing_date
    selected = [
        row
        for row in eligible
        if row.processing_date == newest[(row.report, row.data_date)]
    ]
    coverage = {key: len(processing_dates) for key, processing_dates in snapshots.items()}
    return selected, coverage


def _extract_row_metrics(
    row: ParsedRow,
    spec: ReportSpec,
    *,
    granularity: str,
    gaps: list[GapDraft],
) -> list[tuple[str, Decimal, str, Mapping[str, str], tuple[str, ...]]]:
    extracted: list[tuple[str, Decimal, str, Mapping[str, str], tuple[str, ...]]] = []
    values = row.values

    if spec.grouped_metric is not None:
        grouped = spec.grouped_metric
        dimension_header = _first_header(values, grouped.dimension_headers)
        count_header = _first_header(values, grouped.count_headers)
        if (
            dimension_header is not None
            and count_header is not None
            and values.get(count_header, "")
        ):
            dimension_value = _normalize_text(values.get(dimension_header))
            mapped = grouped.values.get(dimension_value)
            if mapped is None:
                _add_gap(
                    gaps,
                    GapDraft(
                        code="unknown_metric_dimension",
                        severity="warning",
                        report=spec.key,
                        period=_period_mapping(row.data_date, granularity),
                        message="A metric dimension is not in the reviewed v1 allowlist.",
                        evidence_keys={row.evidence_key},
                    ),
                )
            else:
                metric, display_value = mapped
                number = _parse_decimal(
                    values[count_header], integral=True, label=f"{spec.display_name} counts"
                )
                extracted.append(
                    (
                        metric,
                        number,
                        "count",
                        {grouped.dimension_key: display_value},
                        spec.caveats,
                    )
                )

    seen_named_metrics: set[str] = set()
    for named in spec.named_metrics:
        if named.metric in seen_named_metrics:
            continue
        header = _first_header(values, named.headers)
        if header is None or not values.get(header, ""):
            continue
        unit = named.unit
        caveats = list(spec.caveats)
        if named.generic_currency:
            currency = values.get("currency", "").strip().upper()
            if not re.fullmatch(r"[A-Z]{3}", currency):
                _add_gap(
                    gaps,
                    GapDraft(
                        code="missing_currency",
                        severity="warning",
                        report=spec.key,
                        metric=named.metric,
                        message="A currency-denominated metric has no valid ISO currency code.",
                        evidence_keys={row.evidence_key},
                    ),
                )
                continue
            unit = currency
            caveats.append("Currency-specific values are not converted between currencies.")
        number = _parse_decimal(
            values[header],
            integral=named.integral,
            label=f"{spec.display_name} {named.metric}",
        )
        extracted.append((named.metric, number, unit, {}, tuple(caveats)))
        seen_named_metrics.add(named.metric)
    return extracted


def _build_buckets(
    rows: Sequence[ParsedRow],
    *,
    granularity: str,
    as_of: date,
    correction_coverage: Mapping[tuple[str, date], int],
    report_headers: Mapping[str, set[str]],
    gaps: list[GapDraft],
) -> list[Bucket]:
    buckets: dict[tuple[str, str, str, str, date], Bucket] = {}
    currency_units: dict[tuple[str, str, str, date], set[str]] = defaultdict(set)
    reports_with_metrics: set[str] = set()
    incomplete_seen: set[tuple[str, date]] = set()

    for spec in REPORT_SPECS:
        headers = report_headers.get(spec.key, set())
        for metric, aliases in spec.non_additive_headers.items():
            if _first_header(headers, aliases) is not None:
                _add_gap(
                    gaps,
                    GapDraft(
                        code="non_additive_metric",
                        severity="info",
                        report=spec.key,
                        metric=metric,
                        message="This unique metric is not summed across report rows.",
                    ),
                )

    for row in rows:
        spec = REPORT_BY_KEY[row.report]
        if not _complete_period(
            row.data_date,
            spec=spec,
            granularity=granularity,
            as_of=as_of,
            processing_date=row.processing_date,
        ):
            marker = (row.report, row.data_date)
            if marker not in incomplete_seen:
                _add_gap(
                    gaps,
                    GapDraft(
                        code="incomplete_period_excluded",
                        severity="warning",
                        report=row.report,
                        period=_period_mapping(row.data_date, granularity),
                        message=(
                            "This period was excluded because Apple's completeness "
                            "window has not elapsed."
                        ),
                        evidence_keys={row.evidence_key},
                    ),
                )
                incomplete_seen.add(marker)
            continue

        extracted = _extract_row_metrics(
            row, spec, granularity=granularity, gaps=gaps
        )
        if extracted:
            reports_with_metrics.add(row.report)
        for metric, number, unit, dimensions, caveats in extracted:
            dimensions_json = json.dumps(dimensions, sort_keys=True, separators=(",", ":"))
            base_key = (row.report, metric, dimensions_json, row.data_date)
            currency_units[base_key].add(unit)
            key = (row.report, metric, unit, dimensions_json, row.data_date)
            bucket = buckets.get(key)
            if bucket is None:
                bucket = Bucket(
                    report=row.report,
                    metric=metric,
                    unit=unit,
                    dimensions=dict(dimensions),
                    data_date=row.data_date,
                    processing_date=row.processing_date,
                )
                buckets[key] = bucket
            bucket.value = _decimal_add(bucket.value, number)
            bucket.processing_date = max(bucket.processing_date, row.processing_date)
            bucket.evidence_keys.add(row.evidence_key)
            bucket.caveats.update(caveats)
            if correction_coverage.get((row.report, row.data_date), 0) > 1:
                bucket.caveats.add(
                    "Correction coverage included multiple eligible processing "
                    "snapshots; the newest supplied snapshot was selected."
                )
            else:
                bucket.caveats.add(
                    "Correction coverage is limited to one eligible processing "
                    "snapshot for this report period."
                )

    mixed_currency_keys = {
        base_key
        for base_key, units in currency_units.items()
        if len({unit for unit in units if unit != "count" and unit != "seconds"}) > 1
    }
    for report, metric, dimensions_json, data_date in sorted(mixed_currency_keys):
        _add_gap(
            gaps,
            GapDraft(
                code="mixed_currency_separated",
                severity="info",
                report=report,
                metric=metric,
                period=_period_mapping(data_date, granularity),
                message=(
                    "Multiple currencies were present and were emitted as separate "
                    "fact series without conversion."
                ),
            ),
        )

    for spec in REPORT_SPECS:
        if spec.key in report_headers and spec.key not in reports_with_metrics:
            _add_gap(
                gaps,
                GapDraft(
                    code="missing_metric",
                    severity="warning",
                    report=spec.key,
                    message="No supported additive metric was available in a complete period.",
                ),
            )

    return list(buckets.values())


def _assign_evidence_ids(
    evidence: Sequence[EvidenceDraft], privacy: str
) -> tuple[list[dict[str, object]], dict[tuple[int, int, int], str]]:
    ordered = sorted(
        evidence,
        key=lambda item: (
            item.report,
            item.processing_date,
            item.report_date or "",
            item.report_id or "",
            item.instance_id or "",
            item.version or "",
            item.segment_id,
            item.checksum,
        ),
    )
    result: list[dict[str, object]] = []
    identifiers: dict[tuple[int, int, int], str] = {}
    for index, item in enumerate(ordered, start=1):
        evidence_id = f"evidence-{index:04d}"
        identifiers[item.key] = evidence_id
        record: dict[str, object] = {
            "evidenceId": evidence_id,
            "report": item.report,
            "reportDate": item.report_date,
            "processingDate": item.processing_date,
            "granularity": item.granularity,
            "sizeInBytes": item.size,
            "md5": item.checksum,
            "rowCount": item.row_count,
            "compression": item.compression,
            "delimiter": item.delimiter,
        }
        if item.version is not None:
            record["version"] = item.version
        if privacy == "confidential":
            record["reportId"] = item.report_id
            record["instanceId"] = item.instance_id
            record["segmentId"] = item.segment_id
        result.append(record)
    return result, identifiers


def _fact_sort_key(bucket: Bucket) -> tuple[object, ...]:
    return (
        bucket.report,
        bucket.metric,
        bucket.unit,
        json.dumps(bucket.dimensions, sort_keys=True),
        bucket.data_date,
    )


def _build_facts(
    buckets: Sequence[Bucket],
    *,
    granularity: str,
    evidence_ids: Mapping[tuple[int, int, int], str],
    gaps: list[GapDraft],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], list[Bucket]] = defaultdict(list)
    for bucket in buckets:
        dimensions_json = json.dumps(bucket.dimensions, sort_keys=True, separators=(",", ":"))
        grouped[(bucket.report, bucket.metric, bucket.unit, dimensions_json)].append(bucket)

    source_records: list[tuple[Bucket, dict[str, object]]] = []
    selected_groups: dict[tuple[str, str, str, str], list[Bucket]] = {}
    for group_key, group_buckets in grouped.items():
        latest = sorted(group_buckets, key=lambda item: item.data_date)[-2:]
        selected_groups[group_key] = latest
        if len(latest) < 2:
            only = latest[-1] if latest else None
            _add_gap(
                gaps,
                GapDraft(
                    code="insufficient_complete_periods",
                    severity="warning",
                    report=group_key[0],
                    metric=group_key[1],
                    period=(
                        _period_mapping(only.data_date, granularity) if only is not None else None
                    ),
                    message="Two complete buckets are required for a period comparison.",
                    evidence_keys=set(only.evidence_keys) if only is not None else set(),
                ),
            )
        for bucket in latest:
            record: dict[str, object] = {
                "claimClass": "apple_reported",
                "report": bucket.report,
                "metric": bucket.metric,
                "unit": bucket.unit,
                "value": _canonical_decimal(bucket.value),
                "dimensions": dict(sorted(bucket.dimensions.items())),
                "period": _period_mapping(bucket.data_date, granularity),
                "processingDate": bucket.processing_date.isoformat(),
                "evidenceIds": sorted(evidence_ids[key] for key in bucket.evidence_keys),
                "formula": "sum of compatible Standard report rows for the period",
                "caveats": sorted(bucket.caveats),
            }
            source_records.append((bucket, record))

    source_records.sort(key=lambda pair: _fact_sort_key(pair[0]))
    facts: list[dict[str, object]] = []
    source_fact_ids: dict[tuple[str, str, str, str, date], str] = {}
    for index, (bucket, record) in enumerate(source_records, start=1):
        fact_id = f"fact-{index:04d}"
        record = {"factId": fact_id, **record}
        facts.append(record)
        source_fact_ids[
            (
                bucket.report,
                bucket.metric,
                bucket.unit,
                json.dumps(bucket.dimensions, sort_keys=True, separators=(",", ":")),
                bucket.data_date,
            )
        ] = fact_id

    comparison_drafts: list[tuple[tuple[str, str, str, str], dict[str, object]]] = []
    for group_key, latest in selected_groups.items():
        if len(latest) != 2:
            continue
        previous, current = latest
        absolute_change = _decimal_subtract(current.value, previous.value)
        percent_change: str | None
        if previous.value == 0:
            percent_change = None
            _add_gap(
                gaps,
                GapDraft(
                    code="zero_baseline",
                    severity="info",
                    report=current.report,
                    metric=current.metric,
                    period=_period_mapping(previous.data_date, granularity),
                    message="Percent change is unavailable because the previous bucket is zero.",
                    evidence_keys=set(previous.evidence_keys | current.evidence_keys),
                ),
            )
        else:
            percent_change = _canonical_decimal(
                _decimal_percent_change(absolute_change, previous.value)
            )
        current_key = (*group_key, current.data_date)
        previous_key = (*group_key, previous.data_date)
        comparison_evidence = sorted(
            evidence_ids[key] for key in previous.evidence_keys | current.evidence_keys
        )
        caveats = set(previous.caveats | current.caveats)
        caveats.add(
            "The comparison uses the latest two available complete buckets, not a rolling window."
        )
        expected_previous_start = _previous_period_start(
            current.data_date, granularity
        )
        if previous.data_date != expected_previous_start:
            caveats.add("The two latest complete buckets are not consecutive.")
        comparison_drafts.append(
            (
                group_key,
                {
                    "claimClass": "deterministically_derived",
                    "report": current.report,
                    "metric": current.metric,
                    "unit": current.unit,
                    "value": _canonical_decimal(current.value),
                    "previousValue": _canonical_decimal(previous.value),
                    "absoluteChange": _canonical_decimal(absolute_change),
                    "percentChange": percent_change,
                    "dimensions": dict(sorted(current.dimensions.items())),
                    "period": {
                        "current": {
                            **_period_mapping(current.data_date, granularity),
                            "processingDate": current.processing_date.isoformat(),
                            "evidenceIds": sorted(
                                evidence_ids[key] for key in current.evidence_keys
                            ),
                        },
                        "previous": {
                            **_period_mapping(previous.data_date, granularity),
                            "processingDate": previous.processing_date.isoformat(),
                            "evidenceIds": sorted(
                                evidence_ids[key] for key in previous.evidence_keys
                            ),
                        },
                    },
                    "processingDate": current.processing_date.isoformat(),
                    "evidenceIds": comparison_evidence,
                    "sourceFactIds": [
                        source_fact_ids[previous_key],
                        source_fact_ids[current_key],
                    ],
                    "formula": (
                        "current - previous; "
                        "((current - previous) / abs(previous)) * 100"
                    ),
                    "caveats": sorted(caveats),
                },
            )
        )

    comparison_drafts.sort(key=lambda pair: pair[0])
    for offset, (_, record) in enumerate(comparison_drafts, start=len(facts) + 1):
        facts.append({"factId": f"fact-{offset:04d}", **record})
    return facts


def _serialize_gaps(
    gaps: Sequence[GapDraft],
    evidence_ids: Mapping[tuple[int, int, int], str],
) -> list[dict[str, object]]:
    ordered = sorted(
        gaps,
        key=lambda gap: (
            gap.report or "",
            gap.metric or "",
            gap.code,
            json.dumps(gap.period, sort_keys=True) if gap.period else "",
            gap.message,
            tuple(sorted(gap.evidence_keys)),
        ),
    )
    result: list[dict[str, object]] = []
    for index, gap in enumerate(ordered, start=1):
        result.append(
            {
                "gapId": f"gap-{index:04d}",
                "code": gap.code,
                "severity": gap.severity,
                "report": gap.report,
                "metric": gap.metric,
                "period": gap.period,
                "message": gap.message,
                "evidenceIds": sorted(
                    evidence_ids[key]
                    for key in gap.evidence_keys
                    if key in evidence_ids
                ),
            }
        )
    return result


def _json_text(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _write_outputs(output_dir: Path, payloads: Mapping[str, object]) -> dict[str, Path]:
    rendered = {
        key: _json_text(payloads[key])
        for key in ("facts", "evidence_manifest", "gaps")
    }
    paths = {key: output_dir / filename for key, filename in OUTPUT_FILENAMES.items()}
    temporary: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        if output_dir.is_symlink():
            raise EvidenceError("output-dir must not be a symbolic link")
        output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not output_dir.is_dir():
            raise EvidenceError("output-dir is not a directory")
        os.chmod(output_dir, 0o700)

        for destination in paths.values():
            if os.path.lexists(destination):
                if destination.is_symlink() or not destination.is_file():
                    raise EvidenceError(
                        "an evidence output destination is not a regular file"
                    )
                os.chmod(destination, 0o600)

        for key in ("facts", "evidence_manifest", "gaps"):
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=output_dir,
                prefix=f".{OUTPUT_FILENAMES[key]}.",
                delete=False,
            ) as handle:
                handle.write(rendered[key])
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = Path(handle.name)
            os.chmod(temp_path, 0o600)
            temporary.append((temp_path, paths[key]))

        for destination in paths.values():
            if not destination.exists():
                continue
            descriptor, backup_name = tempfile.mkstemp(
                dir=output_dir,
                prefix=f".{destination.name}.backup.",
            )
            os.close(descriptor)
            backup = Path(backup_name)
            backup.unlink()
            try:
                os.replace(destination, backup)
            except OSError:
                backup.unlink(missing_ok=True)
                raise
            backups.append((destination, backup))

        for temp_path, destination in temporary:
            os.replace(temp_path, destination)
            installed.append(destination)
            os.chmod(destination, 0o600)
        for _, backup in backups:
            try:
                backup.unlink(missing_ok=True)
            except OSError:
                # The three public outputs are already consistently committed.
                # Retaining a private backup is safer than rolling back a
                # successfully installed set after the commit point.
                pass
    except OSError as exc:
        rollback_error = False
        for destination in reversed(installed):
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                rollback_error = True
        for destination, backup in reversed(backups):
            if not backup.exists():
                continue
            try:
                os.replace(backup, destination)
                os.chmod(destination, 0o600)
            except OSError:
                rollback_error = True
        for temp_path, _ in temporary:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                rollback_error = True
        for _, backup in backups:
            try:
                backup.unlink(missing_ok=True)
            except OSError:
                rollback_error = True
        message = (
            "evidence outputs could not be written and rollback was incomplete"
            if rollback_error
            else "evidence outputs could not be written; prior outputs were restored"
        )
        raise EvidenceError(message) from exc
    except EvidenceError:
        for temp_path, _ in temporary:
            temp_path.unlink(missing_ok=True)
        raise
    return paths


def build_evidence(
    inventory_path: Path,
    segments_dir: Path,
    output_dir: Path,
    *,
    granularity: str,
    as_of: str,
    privacy: str,
) -> dict[str, Path]:
    """Validate downloaded ASC analytics and build deterministic evidence files."""

    inventory_path = Path(inventory_path)
    segments_dir = Path(segments_dir)
    output_dir = Path(output_dir)
    normalized_granularity = str(granularity).upper()
    normalized_privacy = str(privacy).casefold()
    if normalized_granularity not in SUPPORTED_GRANULARITIES:
        raise EvidenceError("granularity must be DAILY, WEEKLY, or MONTHLY")
    if normalized_privacy not in SUPPORTED_PRIVACY_MODES:
        raise EvidenceError("privacy must be confidential or redacted")
    as_of_date = _parse_iso_date(as_of, "as-of")
    if not inventory_path.is_file():
        raise EvidenceError("inventory path is not a readable file")
    if not segments_dir.is_dir():
        raise EvidenceError("segments-dir is not a readable directory")

    inventory = _load_inventory(inventory_path)
    gaps: list[GapDraft] = [
        GapDraft(
            code="unsupported_concentration_analysis",
            severity="info",
            message=(
                "V1 does not aggregate territory, source, product, or platform "
                "concentration; raw rows must not be used as a fallback."
            ),
        )
    ]
    selected, _ = _select_reports_and_instances(
        inventory,
        granularity=normalized_granularity,
        as_of=as_of_date,
        gaps=gaps,
    )
    rows, evidence_drafts, report_headers = _collect_rows(
        selected,
        segments_dir=segments_dir,
        granularity=normalized_granularity,
        gaps=gaps,
    )
    newest_rows, correction_coverage = _select_newest_partitions(rows, as_of_date)
    buckets = _build_buckets(
        newest_rows,
        granularity=normalized_granularity,
        as_of=as_of_date,
        correction_coverage=correction_coverage,
        report_headers=report_headers,
        gaps=gaps,
    )
    evidence, evidence_ids = _assign_evidence_ids(evidence_drafts, normalized_privacy)
    facts = _build_facts(
        buckets,
        granularity=normalized_granularity,
        evidence_ids=evidence_ids,
        gaps=gaps,
    )
    serialized_gaps = _serialize_gaps(gaps, evidence_ids)

    facts_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "asOf": as_of_date.isoformat(),
        "granularity": normalized_granularity,
        "privacy": normalized_privacy,
        "facts": facts,
    }
    evidence_payload: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "asOf": as_of_date.isoformat(),
        "granularity": normalized_granularity,
        "privacy": normalized_privacy,
        "source": {
            "format": "asc analytics view --include-segments",
            "networkAccess": False,
        },
        "selectionPolicy": {
            "corrections": "newest processingDate per report and report data date",
            "comparisons": "latest two available complete buckets",
            "dailyCompletenessLagDays": {
                spec.key: spec.daily_lag_days for spec in REPORT_SPECS
            },
            "weeklyAndMonthly": "included after represented period end",
        },
        "summary": {
            "verifiedSegments": len(evidence),
            "parsedRows": sum(item.row_count for item in evidence_drafts),
            "factsEmitted": len(facts),
            "gapsFound": len(serialized_gaps),
            "singleSnapshotPeriods": sum(
                1 for count in correction_coverage.values() if count == 1
            ),
            "multipleSnapshotPeriods": sum(
                1 for count in correction_coverage.values() if count > 1
            ),
        },
        "evidence": evidence,
    }
    request_id = _safe_opaque_id(inventory.get("requestId"))
    if normalized_privacy == "confidential" and request_id is not None:
        evidence_payload["requestId"] = request_id

    gaps_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "asOf": as_of_date.isoformat(),
        "granularity": normalized_granularity,
        "privacy": normalized_privacy,
        "gaps": serialized_gaps,
    }
    return _write_outputs(
        output_dir,
        {
            "facts": facts_payload,
            "evidence_manifest": evidence_payload,
            "gaps": gaps_payload,
        },
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build deterministic evidence from downloaded App Store Connect "
            "analytics segments without network access."
        )
    )
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--segments-dir", required=True, type=Path)
    parser.add_argument(
        "--granularity",
        required=True,
        type=str.upper,
        choices=sorted(SUPPORTED_GRANULARITIES),
    )
    parser.add_argument("--as-of", required=True)
    parser.add_argument(
        "--privacy",
        required=True,
        type=str.casefold,
        choices=sorted(SUPPORTED_PRIVACY_MODES),
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        build_evidence(
            args.inventory,
            args.segments_dir,
            args.output_dir,
            granularity=args.granularity,
            as_of=args.as_of,
            privacy=args.privacy,
        )
    except EvidenceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError:
        print("error: local evidence files could not be read or written", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

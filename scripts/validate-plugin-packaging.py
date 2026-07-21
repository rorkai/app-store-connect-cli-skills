#!/usr/bin/env python3
"""Validate the cross-host plugin package without requiring either host CLI."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse


SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CODEX_KEYS = {
    "id",
    "name",
    "version",
    "description",
    "skills",
    "apps",
    "mcpServers",
    "interface",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
}
CODEX_INTERFACE_KEYS = {
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
    "websiteURL",
    "privacyPolicyURL",
    "termsOfServiceURL",
    "brandColor",
    "composerIcon",
    "logo",
    "logoDark",
    "screenshots",
    "defaultPrompt",
    "default_prompt",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Plugin repository root")
    parser.add_argument(
        "--expected-skills",
        type=int,
        default=23,
        help="Expected number of packaged skills (default: 23)",
    )
    return parser.parse_args()


def load_object(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"missing {path}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{path} is not valid JSON: {error}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{path} must contain a JSON object")
        return None
    reject_placeholders(value, str(path), errors)
    return value


def reject_placeholders(value: Any, label: str, errors: list[str]) -> None:
    if isinstance(value, str) and "[TODO:" in value:
        errors.append(f"{label} contains a TODO placeholder")
    elif isinstance(value, list):
        for item in value:
            reject_placeholders(item, label, errors)
    elif isinstance(value, dict):
        for item in value.values():
            reject_placeholders(item, label, errors)


def require_string(payload: dict[str, Any], field: str, label: str, errors: list[str]) -> str | None:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}.{field} must be a non-empty string")
        return None
    return value


def validate_https(payload: dict[str, Any], field: str, label: str, errors: list[str]) -> None:
    value = payload.get(field)
    if value is None:
        return
    parsed = urlparse(value) if isinstance(value, str) else None
    if parsed is None or parsed.scheme != "https" or not parsed.netloc:
        errors.append(f"{label}.{field} must be an absolute HTTPS URL")


def validate_identity(payload: dict[str, Any], label: str, errors: list[str]) -> None:
    name = require_string(payload, "name", label, errors)
    version = require_string(payload, "version", label, errors)
    require_string(payload, "description", label, errors)
    if name is not None and KEBAB_CASE.fullmatch(name) is None:
        errors.append(f"{label}.name must be lowercase kebab-case")
    if version is not None and SEMVER.fullmatch(version) is None:
        errors.append(f"{label}.version must be strict semver")

    author = payload.get("author")
    if not isinstance(author, dict):
        errors.append(f"{label}.author must be an object")
    else:
        require_string(author, "name", f"{label}.author", errors)
        validate_https(author, "url", f"{label}.author", errors)
    for field in ("homepage", "repository"):
        validate_https(payload, field, label, errors)


def validate_relative_directory(root: Path, raw_path: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        errors.append(f"{label} must be a non-empty relative path")
        return None
    posix_path = PurePosixPath(raw_path)
    if posix_path.is_absolute() or ".." in posix_path.parts:
        errors.append(f"{label} must stay inside the plugin root")
        return None
    resolved = (root / posix_path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        errors.append(f"{label} must stay inside the plugin root")
        return None
    if not resolved.is_dir():
        errors.append(f"{label} does not resolve to a directory")
        return None
    return resolved


def validate_codex(root: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    label = ".codex-plugin/plugin.json"
    unknown = sorted(set(manifest) - CODEX_KEYS)
    if unknown:
        errors.append(f"{label} contains unsupported fields: {', '.join(unknown)}")
    validate_identity(manifest, label, errors)
    skills = validate_relative_directory(root, manifest.get("skills"), f"{label}.skills", errors)
    if skills is not None and skills != (root / "skills").resolve():
        errors.append(f"{label}.skills must resolve to the root skills directory")

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append(f"{label}.interface must be an object")
        return
    unknown_interface = sorted(set(interface) - CODEX_INTERFACE_KEYS)
    if unknown_interface:
        errors.append(f"{label}.interface contains unsupported fields: {', '.join(unknown_interface)}")
    for field in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
        require_string(interface, field, f"{label}.interface", errors)
    capabilities = interface.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities or not all(
        isinstance(item, str) and item.strip() for item in capabilities
    ):
        errors.append(f"{label}.interface.capabilities must be a non-empty array of strings")
    prompts = interface.get("defaultPrompt", interface.get("default_prompt"))
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3 or not all(
        isinstance(item, str) and item.strip() and len(item) <= 128 for item in prompts
    ):
        errors.append(f"{label}.interface.defaultPrompt must contain 1-3 non-empty strings of at most 128 characters")


def validate_claude(
    root: Path,
    manifest: dict[str, Any],
    marketplace: dict[str, Any],
    errors: list[str],
) -> None:
    label = ".claude-plugin/plugin.json"
    validate_identity(manifest, label, errors)
    if manifest.get("$schema") != "https://json.schemastore.org/claude-code-plugin-manifest.json":
        errors.append(f"{label} must reference the official Claude Code plugin schema")
    plugin_name = manifest.get("name")
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        errors.append(".claude-plugin/marketplace.json.plugins must be an array")
        return
    matches = [item for item in plugins if isinstance(item, dict) and item.get("name") == plugin_name]
    if len(matches) != 1:
        errors.append("Claude marketplace must contain exactly one entry matching the plugin name")
    elif matches[0].get("source") != "./":
        errors.append("Claude marketplace plugin source must be `./` so the repository root is loadable")


def validate_skills(root: Path, expected: int, errors: list[str]) -> list[Path]:
    skills_root = root / "skills"
    if not skills_root.is_dir():
        errors.append("missing skills directory")
        return []
    skill_dirs = sorted(path for path in skills_root.iterdir() if path.is_dir() and not path.name.startswith("."))
    if len(skill_dirs) != expected:
        errors.append(f"expected {expected} skills, found {len(skill_dirs)}")
    for skill_dir in skill_dirs:
        if not (skill_dir / "SKILL.md").is_file():
            errors.append(f"skill {skill_dir.name} is missing SKILL.md")
    return skill_dirs


def validate(root: Path, expected_skills: int) -> list[str]:
    errors: list[str] = []
    root = root.resolve()
    skill_dirs = validate_skills(root, expected_skills, errors)
    codex = load_object(root / ".codex-plugin" / "plugin.json", errors)
    claude = load_object(root / ".claude-plugin" / "plugin.json", errors)
    marketplace = load_object(root / ".claude-plugin" / "marketplace.json", errors)
    if codex is not None:
        validate_codex(root, codex, errors)
    if claude is not None and marketplace is not None:
        validate_claude(root, claude, marketplace, errors)
    if codex is not None and claude is not None:
        for field in ("name", "version", "repository", "homepage", "license"):
            if codex.get(field) != claude.get(field):
                errors.append(f"Codex and Claude manifests must use the same {field}")
    if not errors and len(skill_dirs) == expected_skills:
        print(
            f"Packaging validation passed: {len(skill_dirs)} skills, "
            f"Codex {codex.get('name')}, Claude {claude.get('name')}, version {codex.get('version')}"
        )
    return errors


def main() -> int:
    args = parse_args()
    errors = validate(Path(args.root), args.expected_skills)
    if errors:
        print("Packaging validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

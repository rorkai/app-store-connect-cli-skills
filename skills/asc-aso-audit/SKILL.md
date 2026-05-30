---
name: asc-aso-audit
description: Run an offline ASO audit on canonical App Store metadata under `./metadata` and surface keyword gaps using Astro MCP. Use after pulling metadata with `asc metadata pull`.
---

# asc ASO audit

Run a two-phase ASO audit: offline checks against local metadata files, then keyword gap analysis via Astro MCP.
When available, include Apple-generated app tags as a discoverability signal.

## Preconditions

- Metadata pulled locally into canonical files via `asc metadata pull --app "APP_ID" --version "1.2.3" --dir "./metadata"`.
- If metadata came from `asc migrate export` or `asc localizations download`, normalize it into the canonical `./metadata` layout before running this skill.
- For Astro gap analysis: app tracked in Astro MCP (optional — offline checks run without it).
- For Apple-generated discoverability tags: `asc app-tags list --app "APP_ID" --output json` works when the API returns tags for the app.

## Before You Start

1. Read `references/aso_rules.md` to understand the rules each check enforces.
2. Identify the **latest version directory** under `metadata/version/` (highest semantic version number). Use this for all version-level fields.
3. The **primary locale** is `en-US` unless the user specifies otherwise.

## Metadata File Paths

- **App-info fields** (`subtitle`): `metadata/app-info/{locale}.json`
- **Version fields** (`keywords`, `description`, `whatsNew`): `metadata/version/{latest-version}/{locale}.json`
- **App name**: May not be present in exported metadata. If `name` is missing from the app-info JSON, fetch it via `asc apps info list` or ask the user. Do not flag it as a missing-field error.

## Phase 1: Offline Checks

Run these 5 checks against the local metadata directory. No network calls required.

### 1. Keyword Waste

Tokenize the `subtitle` field (and `name` if available). Flag any token that also appears in the `keywords` field — it is already indexed and wastes keyword budget.

```
Severity: ⚠️ Warning
Example:  "quran" appears in subtitle AND keywords — remove from keywords to free 6 characters
```

How to check:
1. Read `metadata/app-info/{locale}.json` for `subtitle` (and `name` if present)
2. Read `metadata/version/{latest-version}/{locale}.json` for `keywords`
3. Tokenize subtitle (+ name):
   - **Latin/Cyrillic scripts:** split by whitespace, strip leading/trailing punctuation, lowercase
   - **Chinese/Japanese/Korean:** split by `、` `，` `,` or iterate characters — each character or character-group is a token. Whitespace tokenization does not work for CJK.
   - **Arabic:** split by whitespace, then also generate prefix-stripped variants (remove ال prefix) since Apple likely normalizes definite articles. For example, "القرآن" in subtitle should flag both "القرآن" and "قرآن" in keywords.
4. Split keywords by comma, trim whitespace, lowercase
5. Report intersection (including fuzzy matches from prefix stripping)

### Optional: App Tag Alignment

App tags are Apple-generated labels that can appear in search results and product pages. They are not editable ASO metadata, but they are useful evidence for whether Apple's classification matches the intended positioning.

```bash
asc app-tags list --app "APP_ID" --output json
asc app-tags view --app "APP_ID" --id "TAG_ID" --output json
```

Use tags as context only:
- If visible tags reinforce the subtitle/keyword strategy, note the alignment.
- If tags point to an unintended category or use case, recommend metadata/category changes that may improve future classification.
- Do not promise that changing metadata will immediately change Apple-generated tags.

### 2. Underutilized Fields

Flag fields using less than their recommended minimum:

| Field | Minimum | Limit | Rationale |
|-------|---------|-------|-----------|
| Keywords | 90 chars | 100 | 90%+ usage maximizes indexing |
| Subtitle | 20 chars | 30 | 65%+ usage recommended |

```
Severity: ⚠️ Warning
Example:  keywords is 62/100 characters (62%) — 38 characters of indexing opportunity unused
```

### 3. Missing Fields

Flag empty or missing required fields: `subtitle`, `keywords`, `description`, `whatsNew`.

Note: `name` may not be in the export — only flag it if the app-info JSON explicitly contains a `name` key with an empty value.

```
Severity: ❌ Error
Example:  subtitle is empty for locale en-US
```

### 4. Bad Keyword Separators

Check the `keywords` field for formatting issues:
- Spaces after commas (`quran, recitation`)
- Semicolons instead of commas (`quran;recitation`)
- Pipes instead of commas (`quran|recitation`)

```
Severity: ❌ Error
Example:  keywords contain spaces after commas — wastes 3 characters
```

### 5. Cross-Locale Keyword Gaps

Compare `keywords` fields across all available locales. Flag locales where keywords are identical to the primary locale (`en-US` by default) — this usually means they were not localized.

```
Severity: ⚠️ Warning
Example:  ar keywords identical to en-US — likely not localized for Arabic market
```

How to check:
1. Load keywords for all locales
2. Compare each non-primary locale against the primary
3. Flag exact matches (case-insensitive)

### 6. Description Keyword Coverage

Check whether keywords appear naturally in the `description` field. While Apple does **not** index descriptions for search, users who see their search terms reflected in the description are more likely to download — this improves conversion rate, which indirectly boosts rankings.

```
Severity: 💡 Info
Example:  3 of 16 keywords not found in description: namaz, tarteel, adhan
```

How to check:
1. Load `keywords` and `description` for each locale
2. For each keyword, check if it appears as a substring in the description (case-insensitive)
3. Account for inflected forms: Arabic root matches, verb conjugations (e.g., "memorizar" ≈ "memorices"), and case declensions (e.g., Russian "сура" ≈ "суры")
4. Report missing keywords per locale — recommend weaving them naturally into existing sentences
5. Do NOT flag: Latin-script keywords in non-Latin descriptions (e.g., "quran" in Cyrillic text) — these target separate search paths

## Phase 2: Astro MCP Keyword Gap Analysis

If Astro MCP is available and the app is tracked, run keyword gap analysis. **Run this per store/locale, not just for the US store** — keyword popularity varies dramatically across markets.

### Steps

1. **Get current keywords**: Call `get_app_keywords` with the app ID to retrieve tracked keywords and their current rankings.

2. **Ensure multi-store tracking**: For each locale with a corresponding App Store territory (e.g., `ar-SA` → Saudi Arabia, `fr-FR` → France, `tr` → Turkey), use `add_keywords` to add keyword tracking in that store. Without this, `search_rankings` returns empty for non-US stores.

3. **Extract competitor keywords**: Call `extract_competitors_keywords` with 3-5 top competitor app IDs to find keyword gaps. This is the highest-value Astro tool — it reveals keywords competitors rank for that you don't. Run this per store when possible.

4. **Get suggestions**: Call `get_keyword_suggestions` with the app ID for additional recommendations based on category analysis.

5. **Check current rankings**: Call `search_rankings` to see where the app currently ranks for tracked keywords in each store.

6. **Diff against metadata**: Compare suggested and competitor keywords against the tokens present in `subtitle`, `name` (if available), and `keywords` fields from the local metadata.

7. **Surface gaps**: Report all gaps ranked by popularity score (highest first). Include the source (competitor analysis vs. suggestion).

### Cross-Field Combo Strategy

When recommending keyword additions, consider how single words combine across indexed fields (title + subtitle + keywords). For example:
- Adding "namaz" to keywords when "vakti" is already present enables matching the search "namaz vakti" (66 popularity)
- Adding "holy" to keywords when "Quran" is in the subtitle enables matching "holy quran" (58 popularity)

Flag high-value combos in recommendations.

### Skip Conditions

- Astro MCP not connected → skip with note: "Connect Astro MCP for keyword gap analysis"
- App not tracked in Astro → skip with note: "Add app to Astro with `mcp__astro__add_app` for gap analysis"
- Store not tracked for a locale → add tracking with `add_keywords` before querying

## Output Format

Present results as a single audit report. The report covers only the latest version directory.

```
### ASO Audit Report

**App:** [name] | **Primary Locale:** [locale]
**Metadata source:** [path including version number]

#### Field Utilization

| Field | Value | Length | Limit | Usage |
|-------|-------|--------|-------|-------|
| Name | ... | X | 30 | X% |
| Subtitle | ... | X | 30 | X% |
| Keywords | ... | X | 100 | X% |
| Promotional Text | ... | X | 170 | X% |
| Description | (first 50 chars)... | X | 4000 | X% |

#### Offline Checks

| # | Check | Severity | Field | Locale | Detail |
|---|-------|----------|-------|--------|--------|
| 1 | Keyword waste | ⚠️ | keywords | en-US | "quran" duplicated in subtitle |

**Summary:** X errors, Y warnings across Z locales

#### Keyword Gap Analysis (Astro MCP)

| Keyword | Popularity | In Metadata? | Suggested Action |
|---------|-----------|--------------|-----------------|
| quran recitation | 72 | ❌ | Add to keywords |

#### Recommendations

1. [Highest priority action — errors first]
2. [Next priority — keyword waste]
3. [Utilization improvements]
4. [Keyword gap opportunities]
```

## Notes

- Offline checks work without any network access — they read local files only.
- Astro gap analysis is additive — the audit is useful even without it.
- Run this skill after `asc metadata pull` to ensure canonical metadata files are current.
- For keyword-only follow-up after the audit, prefer the canonical keyword workflow:
  - `asc metadata keywords diff --app "APP_ID" --version "1.2.3" --dir "./metadata"`
  - `asc metadata keywords apply --app "APP_ID" --version "1.2.3" --dir "./metadata" --confirm`
  - `asc metadata keywords sync --app "APP_ID" --version "1.2.3" --dir "./metadata" --input "./keywords.csv"` when importing external keyword research
- After making changes, re-run the audit to verify fixes.
- The Field Utilization table includes promotional text for completeness, but no check validates its content (it is not indexed by Apple).

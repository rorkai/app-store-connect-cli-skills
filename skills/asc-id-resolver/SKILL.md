---
name: asc-id-resolver
description: Resolve App Store Connect IDs (apps, builds, app and digital-goods versions, groups, testers) from human-friendly names using asc. Use when commands require IDs.
---

# asc id resolver

Use this skill to map names to IDs needed by other commands.

## App ID
- By bundle ID or name:
  - `asc apps list --bundle-id "com.example.app"`
  - `asc apps list --name "My App"`
- Fetch everything:
  - `asc apps list --paginate`
- Set default:
  - `ASC_APP_ID=...`

## Build ID
- Latest build:
  - `asc builds info --app "APP_ID" --latest --version "1.2.3" --platform IOS`
- Recent builds:
  - `asc builds list --app "APP_ID" --sort -uploadedDate --limit 5`

## Version ID
- `asc versions list --app "APP_ID" --paginate`

## Digital-goods version IDs

API 4.4.1 version IDs are distinct from IAP product, subscription, and
subscription-group IDs:

- IAP versions: `asc iap versions list --iap-id "IAP_ID" --paginate`
- Subscription versions: `asc subscriptions versions list --subscription-id "SUB_ID" --paginate`
- Subscription group versions: `asc subscriptions groups versions list --group-id "GROUP_ID" --paginate`

Resolve child localization or image IDs from the corresponding version subtree:

- `asc subscriptions versions localizations list --version-id "VERSION_ID" --paginate`

## TestFlight IDs
- Groups:
  - `asc testflight groups list --app "APP_ID" --paginate`
- Testers:
  - `asc testflight testers list --app "APP_ID" --paginate`

## Pre-release version IDs
- `asc testflight pre-release list --app "APP_ID" --platform IOS --paginate`

## Review submission IDs
- `asc review submissions-list --app "APP_ID" --paginate`

## Output tips
- JSON is default; use `--pretty` for debug.
- For human viewing, use `--output table` or `--output markdown`.

## Guardrails
- Prefer `--paginate` on list commands to avoid missing IDs.
- Use `--sort` where available to make results deterministic.

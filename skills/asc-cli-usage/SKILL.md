---
name: asc-cli-usage
description: Guidance for using asc cli in this repo (flags, output formats, pagination, auth, and discovery). Use when asked to run or design asc commands or interact with App Store Connect via the CLI.
---

# asc cli usage

Use this skill when you need to run or design `asc` commands for App Store Connect.

## Command discovery
- Always use `--help` to discover commands and flags.
  - `asc --help`
  - `asc builds --help`
  - `asc builds list --help`
- Use `asc search` for local, deterministic command discovery when you know the workflow but not the command path.
  - `asc search "submit app for review"`
  - `asc search --output table "upload build"`
- Use `asc schema` to inspect bundled App Store Connect endpoint schemas and request/query fields before designing API-facing commands.
  - `asc schema --pretty "GET /v1/apps"`
  - `asc schema --method POST appStoreVersions`
- Use `asc capabilities` to explain CLI-supported, partial, web-only, and public-API-limited workflow coverage.
  - `asc capabilities --area release --output table`
  - `asc capabilities --status not-public-api --output markdown`

## Canonical verbs (current asc)
- Prefer `view` over legacy `get` aliases for read-only commands in docs and automation.
  - `asc apps view --id "APP_ID"`
  - `asc versions view --version-id "VERSION_ID"`
  - `asc pricing availability view --app "APP_ID"`
- Prefer `edit` for update-only availability surfaces and other canonical edit flows.
  - `asc pricing availability edit --app "APP_ID" --territory "USA,GBR" --available true`
  - `asc app-setup availability edit --app "APP_ID" --territory "USA,GBR" --available true`
  - `asc xcode version edit --build-number "42"`
- Keep `set` where the CLI intentionally models a higher-level replacement/configuration flow and `--help` still shows `set` as the canonical verb.

## Flag conventions
- Use explicit long flags (e.g., `--app`, `--output`).
- Prefer explicit flags in automation; some newer commands can prompt for missing fields when run interactively.
- Destructive operations require `--confirm`.
- Use `--paginate` when the user wants all pages.

## Output formats
- Output defaults are TTY-aware: `table` in interactive terminals, `json` when piped or non-interactive.
- Use `--output table` or `--output markdown` only for human-readable output.
- `--pretty` is only valid with JSON output.

## Authentication and defaults
- Prefer keychain auth via `asc auth login`.
- Fallback env vars: `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_PRIVATE_KEY_PATH`, `ASC_PRIVATE_KEY`, `ASC_PRIVATE_KEY_B64`.
- `ASC_APP_ID` can provide a default app ID.
- When permissions are unclear, inspect exact API key role coverage with `asc web auth capabilities`.
  - This lives under the experimental web auth surface.
  - It can resolve the current local auth by default, or inspect a specific key with `--key-id`.

## Timeouts
- `ASC_TIMEOUT` / `ASC_TIMEOUT_SECONDS` control request timeouts.
- `ASC_UPLOAD_TIMEOUT` / `ASC_UPLOAD_TIMEOUT_SECONDS` control upload timeouts.

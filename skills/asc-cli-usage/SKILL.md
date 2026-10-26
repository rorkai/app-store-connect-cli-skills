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
- Use `asc capabilities` to explain CLI-supported, partial, web-session, and public-API-limited workflow coverage.
  - `asc capabilities --area release --output table`
  - `asc capabilities --status web-session --output table`
  - `asc capabilities --status not-public-api --output markdown`

## Prefer native commands over `asc api`
- Use a native command for every read and write. Find it with `asc search "TASK"` or `--help` before reaching for `asc api`.
- For native reads that support `--include`, use it to fetch related records in one call instead of one request per relationship. Use `--output json` to inspect related resources in the `included` array.
  - `asc versions view --version-id "VERSION_ID" --include build,appStoreVersionSubmission`
  - `asc builds info --build-id "BUILD_ID" --include buildBetaDetail,betaAppReviewSubmission,betaGroups`
  - `asc iap view --id "IAP_ID" --include inAppPurchaseLocalizations,appStoreReviewScreenshot`
  - `asc review submissions-get --id "SUBMISSION_ID" --include items,appStoreVersionForReview`
- Single-resource and child-list reads have their own commands, such as `asc localizations view --id "LOCALIZATION_ID"`, `asc testflight groups builds list --group-id "GROUP_ID"`, and `asc pricing availability territory-availabilities --app "APP_ID"`.
- Use `asc api <METHOD> <PATH>` only when no native command covers the task. Its writes require `--confirm`. Do not hand-write `curl` requests with `asc auth token`.

## Canonical verbs (current asc)
- Prefer `view` over legacy `get` aliases for read-only commands in docs and automation.
  - `asc apps view --id "APP_ID"`
  - `asc versions view --version-id "VERSION_ID" --include build`
  - Without `--include`, `asc versions view` prints a deprecated summary; JSON output also warns on stderr. Use `--include build` instead of `--include-build` and `--include appStoreVersionSubmission` instead of `--include-submission`.
  - `asc pricing availability view --app "APP_ID"`
- Prefer `edit` for update-only availability surfaces and other canonical edit flows.
  - `asc pricing availability edit --app "APP_ID" --territory "USA,GBR" --available true`
  - `asc app-setup availability edit --app "APP_ID" --territory "USA,GBR" --available true`
  - `asc xcode version edit --build-number "42"`
- Use `asc pricing availability create` to initialize app availability before using the update-only `edit` command. If Apple rejects the public-API bootstrap, authenticate a web session and use `asc web apps availability create`, or configure Pricing and Availability in App Store Connect.
  - `asc pricing availability create --app "APP_ID" --territory "USA,GBR" --available true --available-in-new-territories true`
  - `asc web apps availability create --app "APP_ID" --territory "USA,GBR" --available-in-new-territories true`
- Keep `set` where the CLI intentionally models a higher-level replacement/configuration flow and `--help` still shows `set` as the canonical verb.

## Flag conventions
- Use explicit long flags (e.g., `--app`, `--output`).
- Prefer explicit flags in automation; some newer commands can prompt for missing fields when run interactively.
- Destructive operations require `--confirm`.
- Use `--paginate` when the user wants all pages.
- Put command-specific flags after the leaf subcommand; parent command groups reject misplaced flags.
- Treat `--next` URLs as opaque continuations. Do not combine them with new filters, sorting, or page-size flags; follow the selected command's help for required selectors.

## Output formats
- Output defaults are TTY-aware: `table` in interactive terminals, `json` when piped or non-interactive.
- Use `--output table` or `--output markdown` only for human-readable output.
- `--pretty` is only valid with JSON output.
- Check the exit status as well as stdout. Failed batch operations can emit partial receipts; inspect completed actions and resource IDs before retrying mutations.

## Authentication and defaults
- Prefer keychain auth via `asc auth login`.
- Fallback env vars: `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_PRIVATE_KEY_PATH`, `ASC_PRIVATE_KEY`, `ASC_PRIVATE_KEY_B64`.
- `ASC_APP_ID` can provide a default app ID.
- App Store Server API reads (transactions, subscription status, refunds, notification history) live under `asc storekit` and use separate In-App Purchase keys registered with `asc storekit auth login`, not `asc auth` profiles.
- When permissions are unclear, inspect exact API key role coverage with `asc web auth capabilities`.
  - This lives under the web-session auth surface.
  - It can resolve the current local auth by default, or inspect a specific key with `--key-id`.
- Create an App Store Connect team API key through a cached Apple Account web session with `asc web api-keys create`.
  - An Account Holder or Admin session is required; use `asc web auth login --apple-id "user@example.com"` first when needed.
  - The command saves the one-time P8 as `AuthKey_<KEY_ID>.p8` without printing its contents; choose an explicit private directory with `--output-dir`.
  - Example: `asc web api-keys create --name "CI uploads" --role APP_MANAGER --output-dir "./keys" --output json`.

## Reuse authentication before requesting another code
- API-key authentication (`asc auth`) and Apple Account web sessions (`asc web auth`) are separate. Prefer the existing keychain API profile for supported operations; inspect `asc auth status` and command capabilities before starting a web login. A profile name is a local label, not an app-level permission boundary.
- For web-only work, check `asc web auth status --apple-id "user@example.com" --output json` first. Reuse an authenticated cached session and verify its provider matches the intended account before mutations. Do not log out or clear trust/session state as routine preparation.
- Give one process ownership of an interactive sign-in for an Apple Account. While a code prompt is pending, continue that same process; coordinate or serialize other agents instead of starting another login that may invalidate its challenge.
- Match a code to the current prompt. A trusted-device notification code and an SMS fallback code belong to different verification steps. Once the CLI announces phone delivery, use the newly delivered phone code, not the earlier notification code. Do not deliberately submit bad codes as a normal resend strategy; inspect the installed command's help for supported recovery.
- On failure, distinguish code rejection from a timeout after verification or provider selection. Inspect the exact error and installed version before requesting more codes. Increasing a request timeout is not proof that an interactive-session problem is fixed.
- After login, verify `authenticated` and the selected provider with a separate status read; confirm the next web operation reuses the cache before reporting success. Apple may expire sessions later, so do not promise permanent unattended authentication.
- Inspect `asc web auth login --help` before configuring a supported `--two-factor-code-command`. Keep credentials and codes out of logs, source, shell history, and PRs. Do not assume a password-manager passkey can be supplied to the CLI or that browser sign-in refreshes its cache; use only authentication mechanisms explicitly supported by the installed CLI.
- A fresh non-interactive web sign-in requires `--two-factor-code-command` or `ASC_WEB_2FA_CODE_COMMAND`; without one it fails before sending the password. Cached-session reuse does not require a fresh sign-in.
- Select a public team ID with `--public-provider-id`; `--provider-id` takes Apple's numeric provider ID. Do not substitute an API profile name for either ID.

## Apple Ads
- Use `asc ads --help` before choosing a command.
- Apple Ads uses `asc ads auth`, `--ads-profile`, and `ASC_ADS_*` variables. It does not use App Store Connect API credentials.
- Direct resource commands use Platform API v1 with `--ad-account` or `ASC_ADS_AD_ACCOUNT_ID`. Deprecated Campaign Management API v5 commands live under `asc ads v5` and use `--org` or `ASC_ADS_ORG_ID`; never substitute one ID for the other.
- Discover ad-account access with `asc ads auth discover --output json` or inspect one ACL response with `asc ads acls list --output json`.
- Body commands use `--file` with the exact schema named by the leaf help. V1 query filters use singular `value`, and bulk bodies may use wrapper objects rather than v5 arrays.
- Apple Ads resource commands emit JSON. Use `--paginate` only where help shows it; reports and most query bodies carry pagination inside the JSON file.
- Deletes and spend-, billing-, delivery-, targeting-, or access-sensitive mutations require `--confirm`. An explicitly paused campaign create is the main documented safe exception.
- For live mutation tests, create paused resources with a clear test name, save every ID, pause spend-bearing resources first, and delete only resources created by the test.

## Timeouts
- `ASC_TIMEOUT` / `ASC_TIMEOUT_SECONDS` control request timeouts.
- `ASC_UPLOAD_TIMEOUT` / `ASC_UPLOAD_TIMEOUT_SECONDS` control upload timeouts.

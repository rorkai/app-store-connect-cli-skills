---
name: asc-release-flow
description: Determine whether an app is ready to submit, then drive the current App Store release flow with asc, including validation, staging, review submission, first-time availability, subscriptions, IAP, Game Center, and App Privacy checks.
---

# Release flow (readiness-first)

Use this skill when the question is "Can my app be submitted now?" or when the user wants to prepare and submit an App Store version with the current `asc` command surface.

## Preconditions

- Resolve `APP_ID`, version string, `VERSION_ID` when needed, and `BUILD_ID` up front.
- Ensure auth is configured with `asc auth login` or `ASC_*` environment variables.
- Have canonical metadata in `./metadata` when using metadata-driven staging.
- Treat `asc web ...` commands as optional web-session fallbacks for flows not covered by the public API.

## Answer order

1. Say whether the app is ready right now.
2. Name the blocking issues.
3. Separate public-API fixes from web-session or manual fixes.
4. Give the next exact command to run.

Blockers usually fall into:

- API-fixable: build validity, metadata, screenshots, review details, content rights, encryption, version/build attachment, IAP readiness, Game Center version and review-submission items.
- Web-session-fixable: initial app availability bootstrap, first-review subscription attachment, App Privacy publish state.
- Manual fallback: first-time IAP selection on the app-version page when no CLI attach flow exists, or any flow the user does not want to run through web-session commands.

## Canonical current path

### 1. Readiness check

Use `asc validate`; the old submit-preflight shortcut is not part of the current CLI.

```bash
asc validate --app "APP_ID" --version "1.2.3" --platform IOS --output table
```

Use strict mode when warnings should block automation:

```bash
asc validate --app "APP_ID" --version "1.2.3" --platform IOS --strict --output table
```

For apps selling digital goods, run the product readiness checks too:

```bash
asc validate iap --app "APP_ID" --output table
asc validate subscriptions --app "APP_ID" --output table
```

### 2. Stage without submitting

Use `asc release stage` when the user wants to prepare the version, apply/copy metadata, attach the build, and validate, while stopping before review submission.

```bash
asc release stage \
  --app "APP_ID" \
  --version "1.2.3" \
  --build "BUILD_ID" \
  --metadata-dir "./metadata/version/1.2.3" \
  --dry-run \
  --output table
```

Apply the staging mutations after the plan looks correct:

```bash
asc release stage \
  --app "APP_ID" \
  --version "1.2.3" \
  --build "BUILD_ID" \
  --metadata-dir "./metadata/version/1.2.3" \
  --confirm
```

Use `--copy-metadata-from "1.2.2"` instead of `--metadata-dir` when carrying metadata forward from an existing version.

### 3. Submit an already prepared version

Use `asc review submit` for explicit App Store review submission. It wraps build attachment plus review submission creation.

```bash
asc review submit --app "APP_ID" --version "1.2.3" --build "BUILD_ID" --dry-run --output table
asc review submit --app "APP_ID" --version "1.2.3" --build "BUILD_ID" --confirm
```

Use `--version-id "VERSION_ID"` instead of `--version` when you already resolved the exact version ID.

### 4. One-command upload and submit

Use `asc publish appstore` when upload/build/local-build and submission should be one high-level flow.

```bash
asc publish appstore --app "APP_ID" --ipa "./App.ipa" --version "1.2.3" --submit --dry-run --output table
asc publish appstore --app "APP_ID" --ipa "./App.ipa" --version "1.2.3" --submit --confirm
```

Add `--wait` when the command should wait for build processing before attaching/submitting.

### 5. Monitor and cancel

```bash
asc status --app "APP_ID"
asc submit status --version-id "VERSION_ID"
asc submit status --id "SUBMISSION_ID"
asc submit cancel --id "SUBMISSION_ID" --confirm
```

## First-time submission blockers

### Initial app availability does not exist

Symptoms:

- `asc pricing availability view --app "APP_ID"` reports no availability.
- `asc pricing availability edit ...` cannot update because there is no existing availability record.

Check:

```bash
asc pricing availability view --app "APP_ID"
```

Bootstrap the first availability record with the web-session flow:

```bash
asc web apps availability create \
  --app "APP_ID" \
  --territory "USA,GBR" \
  --available-in-new-territories true
```

After bootstrap, use the public API for ongoing changes:

```bash
asc pricing availability edit \
  --app "APP_ID" \
  --territory "USA,GBR" \
  --available true \
  --available-in-new-territories true
```

### Subscriptions are ready but not attached to first review

Check subscription readiness first:

```bash
asc validate subscriptions --app "APP_ID" --output table
```

If diagnostics report missing metadata, fix those prerequisites before attaching. Common misses are broad pricing coverage, review screenshots, promotional images, and app/build evidence.

List first-review subscription state:

```bash
asc web review subscriptions list --app "APP_ID"
```

Attach a group for first review:

```bash
asc web review subscriptions attach-group \
  --app "APP_ID" \
  --group-id "GROUP_ID" \
  --confirm
```

Attach one subscription instead:

```bash
asc web review subscriptions attach \
  --app "APP_ID" \
  --subscription-id "SUB_ID" \
  --confirm
```

For later reviews, submit subscriptions through the public review path:

```bash
asc subscriptions review submit --subscription-id "SUB_ID" --confirm
```

### In-app purchases need review readiness or first-version inclusion

```bash
asc validate iap --app "APP_ID" --output table
```

Upload missing review screenshots:

```bash
asc iap review-screenshots create --iap-id "IAP_ID" --file "./review.png"
```

For IAPs on a published app:

```bash
asc iap submit --iap-id "IAP_ID" --confirm
```

For the first IAP on an app, or the first time adding a new IAP type, Apple may require selecting the IAP from the app version's "In-App Purchases and Subscriptions" section before submitting the app version. Prepare the IAP with localization, pricing, and review screenshot data first.

For non-renewing IAPs that must be attached to the next app version review, the public API may reject the review item path. The CLI exposes a web-session fallback that mirrors the App Store Connect web flow:

```bash
asc web review iaps attach --app "APP_ID" --iap-id "IAP_ID" --confirm
```

Use this only for the web-only first-version selection gap, and call out that it requires an authenticated Apple web session.

### Game Center needs app-version and review-submission items

```bash
asc game-center app-versions list --app "APP_ID"
asc game-center app-versions create --app-store-version-id "VERSION_ID"
```

If Game Center component versions must ship with the app version, use the explicit review-submission API so all items can be added before submission:

```bash
asc review submissions-create --app "APP_ID" --platform IOS
asc review items add --submission "SUBMISSION_ID" --item-type appStoreVersions --item-id "VERSION_ID"
asc review items add --submission "SUBMISSION_ID" --item-type gameCenterLeaderboardVersions --item-id "GC_LEADERBOARD_VERSION_ID"
asc review submissions-submit --id "SUBMISSION_ID" --confirm
```

`asc review items add` also supports `gameCenterAchievementVersions`, `gameCenterActivityVersions`, `gameCenterChallengeVersions`, and `gameCenterLeaderboardSetVersions`.

### App Privacy is still unpublished

The public API can surface privacy advisories, but it cannot fully verify App Privacy publish state.

```bash
asc web privacy pull --app "APP_ID" --out "./privacy.json"
asc web privacy plan --app "APP_ID" --file "./privacy.json"
asc web privacy apply --app "APP_ID" --file "./privacy.json"
asc web privacy publish --app "APP_ID" --confirm
```

If the user avoids web-session commands, confirm App Privacy manually in App Store Connect:

```text
https://appstoreconnect.apple.com/apps/APP_ID/appPrivacy
```

### Review details are incomplete

```bash
asc review details-for-version --version-id "VERSION_ID"
```

Create or update details:

```bash
asc review details-create \
  --version-id "VERSION_ID" \
  --contact-first-name "Dev" \
  --contact-last-name "Support" \
  --contact-email "dev@example.com" \
  --contact-phone "+1 555 0100" \
  --notes "Explain the reviewer access path here."

asc review details-update \
  --id "DETAIL_ID" \
  --notes "Updated reviewer instructions."
```

Only set demo-account fields when App Review truly needs demo credentials.

## Ready checklist

An app is effectively ready when:

- `asc validate --app "APP_ID" --version "VERSION" --platform IOS` has no blocking issues.
- `asc release stage --dry-run` produces the expected plan, or `asc release stage --confirm` has successfully prepared the target version.
- The build is `VALID` and attached to the target version.
- Metadata, screenshots, app info, content rights, encryption, age rating, and review details are complete.
- App availability exists.
- Digital goods have localization, pricing, review screenshots, and any first-review attachments or manual selections handled.
- Game Center app-version and component review items are included when needed.
- App Privacy is confirmed or published.

## Notes

- Do not use the legacy submit-preflight, submit-create, or release-run shortcuts; they are not part of the current CLI.
- Use `asc validate` for readiness.
- Use `asc release stage` for pre-submit preparation.
- Use `asc review submit` for explicit App Store review submission.
- Use `asc publish appstore --submit --confirm` for high-level upload plus submission.
- Use `asc status` and `asc submit status` after submission.

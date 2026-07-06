---
name: asc-submission-health
description: Validate App Store submission readiness, submit prepared versions, and monitor review status with current asc commands. Use when shipping or troubleshooting review submissions.
---

# asc submission health

Use this skill to reduce review submission failures and monitor review state. The current readiness command is `asc validate`; legacy submit-preflight and submit-create shortcuts must not be used.

## Preconditions

- Auth configured and app/version/build IDs resolved.
- Build processing completed or the command uses a high-level flow with `--wait`.
- Metadata, app info, screenshots, review details, content rights, encryption, pricing, and availability are expected to be complete.

## Pre-submission checklist

### 1. Verify build status

```bash
asc builds info --build-id "BUILD_ID"
```

Check:

- `processingState` is `VALID`.
- encryption fields are understood before submission.

### 2. Run canonical readiness validation

```bash
asc validate --app "APP_ID" --version "1.2.3" --platform IOS --output table
```

Use strict mode when warnings should fail automation:

```bash
asc validate --app "APP_ID" --version "1.2.3" --platform IOS --strict --output table
```

If you already have the exact version ID:

```bash
asc validate --app "APP_ID" --version-id "VERSION_ID" --platform IOS --output table
```

### 3. Encryption compliance

If the build uses non-exempt encryption:

```bash
asc encryption declarations list --app "APP_ID"

asc encryption declarations create \
  --app "APP_ID" \
  --app-description "Uses standard HTTPS/TLS" \
  --contains-proprietary-cryptography=false \
  --contains-third-party-cryptography=true \
  --available-on-french-store=true

asc encryption declarations assign-builds \
  --id "DECLARATION_ID" \
  --build "BUILD_ID"
```

If the app truly uses only exempt transport encryption, prefer updating the local plist and rebuilding:

```bash
asc encryption declarations exempt-declare --plist "./Info.plist"
```

### 4. Content rights declaration

```bash
asc apps content-rights view --app "APP_ID"
asc apps content-rights edit --app "APP_ID" --uses-third-party-content=false
```

### 5. Version metadata and localizations

```bash
asc versions view --version-id "VERSION_ID" --include-build --include-submission
asc localizations list --version "VERSION_ID" --output table
```

For canonical metadata repair:

```bash
asc metadata pull --app "APP_ID" --version "1.2.3" --platform IOS --dir "./metadata"
asc metadata validate --dir "./metadata" --output table
asc metadata push --app "APP_ID" --version "1.2.3" --platform IOS --dir "./metadata" --dry-run --output table
asc metadata push --app "APP_ID" --version "1.2.3" --platform IOS --dir "./metadata"
```

### 6. App info localizations and privacy policy

```bash
asc apps info list --app "APP_ID" --output table
asc localizations list --app "APP_ID" --type app-info --app-info "APP_INFO_ID" --output table
```

For subscription or IAP apps, make sure privacy policy URL is populated:

```bash
asc app-setup info set --app "APP_ID" --primary-locale "en-US" --privacy-policy-url "https://example.com/privacy"
```

### 7. Screenshots

```bash
asc screenshots list --version-localization "LOC_ID" --output table
asc screenshots sizes --output table
asc screenshots validate --path "./screenshots" --device-type "IPHONE_65" --output table
```

### 8. Digital goods readiness

```bash
asc validate iap --app "APP_ID" --output table
asc validate subscriptions --app "APP_ID" --output table
```

Use JSON when you need exact diagnostics:

```bash
asc validate subscriptions --app "APP_ID" --output json --pretty
```

### 9. App Privacy advisory

The public API cannot fully verify App Privacy publish state. If validation reports an advisory, use the web-session flow or confirm manually.

```bash
asc web privacy pull --app "APP_ID" --out "./privacy.json"
asc web privacy plan --app "APP_ID" --file "./privacy.json"
asc web privacy apply --app "APP_ID" --file "./privacy.json"
asc web privacy publish --app "APP_ID" --confirm
```

Manual fallback:

```text
https://appstoreconnect.apple.com/apps/APP_ID/appPrivacy
```

## Submit

### Submit a prepared version

Use `asc review submit` for explicit App Store review submission:

```bash
asc review submit --app "APP_ID" --version "1.2.3" --build "BUILD_ID" --dry-run --output table
asc review submit --app "APP_ID" --version "1.2.3" --build "BUILD_ID" --confirm
```

Use `--version-id "VERSION_ID"` when you have already resolved the version.

### Upload and submit in one flow

```bash
asc publish appstore --app "APP_ID" --ipa "./App.ipa" --version "1.2.3" --submit --dry-run --output table
asc publish appstore --app "APP_ID" --ipa "./App.ipa" --version "1.2.3" --submit --confirm
```

Add `--wait` when the command should wait for build processing.

### Multi-item review submissions

Use the lower-level review-submission API when the submission needs multiple review items, such as Game Center component versions:

```bash
asc review submissions-create --app "APP_ID" --platform IOS
asc review items add --submission "SUBMISSION_ID" --item-type appStoreVersions --item-id "VERSION_ID"
asc review items add --submission "SUBMISSION_ID" --item-type gameCenterChallengeVersions --item-id "GC_CHALLENGE_VERSION_ID"
asc review submissions-submit --id "SUBMISSION_ID" --confirm
```

For non-renewing IAPs that Apple requires to be selected with the next app version, the public API can reject both direct review items and standalone IAP submission. After validating IAP readiness, use the web-session attachment only for that web-only gap:

```bash
asc web review iaps attach --app "APP_ID" --iap-id "IAP_ID" --confirm
```

This command requires an authenticated Apple web session and should be documented in the handoff.

## Monitor

```bash
asc status --app "APP_ID"
asc submit status --id "SUBMISSION_ID"
asc submit status --version-id "VERSION_ID"
asc review submissions-list --app "APP_ID" --paginate
```

## Cancel and retry

```bash
asc submit cancel --id "SUBMISSION_ID" --confirm
asc submit cancel --version-id "VERSION_ID" --app "APP_ID" --confirm
asc review submissions-cancel --id "SUBMISSION_ID" --confirm
```

Fix validation issues, then submit again with `asc review submit` or `asc publish appstore --submit --confirm`.

## Common submission errors

### Version is not in valid state

Check:

1. Build is attached and `VALID`.
2. Encryption declaration is resolved or exempt.
3. Content rights declaration is set.
4. Required localizations and screenshots are present.
5. Review details are present.
6. Pricing and availability exist.
7. App Privacy has been reviewed and published in App Store Connect.

### Export compliance must be approved

Either upload export compliance documentation or rebuild with exempt encryption metadata if that accurately describes the app.

### Multiple app infos found

Use the exact app-info ID:

```bash
asc apps info list --app "APP_ID" --output table
```

## Notes

- Do not use legacy submit-preflight or submit-create shortcuts; they are removed.
- Use `asc validate` for readiness.
- Use `asc review submit` for prepared-version submission.
- Use `asc publish appstore --submit --confirm` for high-level upload plus submission.
- App Privacy publish state is not fully verifiable through the public API.
- Use `--output table` for human status and JSON for automation.
- macOS submissions follow the same review flow but use `--platform MAC_OS`.

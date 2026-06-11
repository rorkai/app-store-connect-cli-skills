---
name: asc-agent-ios-release
description: Use when an agent should publish or submit an iOS App Store version through the asc CLI instead of the App Store Connect web UI, including build/version resolution, metadata staging, review submission, and hard status verification.
---

# Agent iOS release with asc

Use this skill when a user asks to ship an iOS app, submit an App Store version,
or replace manual App Store Connect clicks with the `asc` CLI.

## Operating rules

- Prefer CLI automation over browser UI for normal release work.
- Verify current flags with `asc --help` and command-specific `--help` before
  running a mutating command.
- Resolve `APP_ID`, `VERSION`, `VERSION_ID`, and `BUILD_ID` before submission.
- Use `--dry-run` first when a command supports it, then use `--confirm`.
- Treat legal agreements, payment, Apple ID 2FA, CAPTCHA, government filing, and
  account-holder attestations as stop points.
- Never print API keys, private keys, passwords, phone numbers, or personal
  identity values in final handoffs.
- Do not call the release complete until the CLI or App Store Connect reports the
  exact version/build and a hard state such as `WAITING_FOR_REVIEW`.

## Release path

1. Confirm auth and app identity:

```bash
asc auth status
asc apps list --bundle-id "com.example.app" --output table
```

2. Resolve the target version and build:

```bash
asc versions list --app "$APP_ID" --platform IOS --output json
asc builds info --app "$APP_ID" --latest --version "$VERSION" --platform IOS --output json
```

3. Validate readiness:

```bash
asc validate --app "$APP_ID" --version "$VERSION" --platform IOS --output table
```

For apps with digital goods, also check products:

```bash
asc validate iap --app "$APP_ID" --output table
asc validate subscriptions --app "$APP_ID" --output table
```

4. Stage metadata and build attachment without submission:

```bash
asc release stage \
  --app "$APP_ID" \
  --version "$VERSION" \
  --build "$BUILD_ID" \
  --copy-metadata-from "$PREVIOUS_VERSION" \
  --dry-run \
  --output table
```

Apply the plan:

```bash
asc release stage \
  --app "$APP_ID" \
  --version "$VERSION" \
  --build "$BUILD_ID" \
  --copy-metadata-from "$PREVIOUS_VERSION" \
  --confirm
```

5. Submit for review:

```bash
asc review submit \
  --app "$APP_ID" \
  --version "$VERSION" \
  --build "$BUILD_ID" \
  --dry-run \
  --output table
```

```bash
asc review submit \
  --app "$APP_ID" \
  --version "$VERSION" \
  --build "$BUILD_ID" \
  --confirm
```

6. Verify hard status:

```bash
asc submit status --version-id "$VERSION_ID" --output table
asc versions view --version-id "$VERSION_ID" --output json
```

Report the final state only after seeing the version/build and review status.

## One-command path

When the IPA is local and the user wants upload plus submission in one flow:

```bash
asc publish appstore \
  --app "$APP_ID" \
  --ipa "./build/ios/ipa/App.ipa" \
  --version "$VERSION" \
  --wait \
  --submit \
  --dry-run \
  --output table
```

```bash
asc publish appstore \
  --app "$APP_ID" \
  --ipa "./build/ios/ipa/App.ipa" \
  --version "$VERSION" \
  --wait \
  --submit \
  --confirm
```

## Handoff shape

Include:

- App name or bundle ID.
- App Store app ID.
- Version and build number.
- Submission ID or version ID when available.
- Exact observed status.
- Any blocker that requires a human account holder.

Avoid:

- Secrets or personal account values.
- Saying "submitted" when only metadata was saved or a draft submission exists.

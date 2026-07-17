---
name: asc-xcode-build
description: Build, archive, generate export options, export, upload, and manage Xcode version/build numbers with the current asc xcode helpers before App Store Connect upload or submission. Use when creating an IPA or PKG for upload.
---

# Xcode build and export

Use this skill when you need to build an app from source and prepare it for App Store Connect. Prefer `asc xcode archive` and `asc xcode export` over raw `xcodebuild` recipes when they fit the project.

## Preconditions

- Xcode and command line tools are installed.
- Signing identity and provisioning profiles are available, or automatic signing is enabled.
- App Store Connect auth is configured when upload or build lookup is needed.

## Manage version and build numbers

```bash
asc xcode version view
asc xcode version edit --version "1.3.0" --build-number "42"
asc xcode version edit --next-build-number --app "APP_ID" --platform IOS
asc xcode version bump --type build
asc xcode version bump --type patch
asc xcode version bump --type build --next-build-number --app "APP_ID" --platform IOS
```

Use `--project-dir "./MyApp"` when not running from the project root. Use `--project "./MyApp/App.xcodeproj"` when the directory contains multiple projects. Use `--target "App"` and `--configuration "Release"` for deterministic reads and writes in multi-target or multi-configuration projects.

To avoid low build-number rejects, resolve and apply the remote-safe build number in one command:

```bash
asc xcode version edit --next-build-number --app "APP_ID" --platform IOS --output json
```

Version mutations validate the full change before writing and return structured output identifying the configurations and files changed. The editor follows recursive xcconfig includes and preserves unrelated project and xcconfig content. Use `asc builds next-build-number` separately when you only want to inspect the remote-safe value without changing the project.

## Preferred iOS/tvOS/visionOS build flow

### 1. Archive with asc

```bash
asc xcode archive \
  --workspace "App.xcworkspace" \
  --scheme "App" \
  --configuration Release \
  --clean \
  --archive-path ".asc/artifacts/App.xcarchive" \
  --xcodebuild-flag=-destination \
  --xcodebuild-flag=generic/platform=iOS \
  --output json
```

Use `--project "App.xcodeproj"` instead of `--workspace` for project-only apps.

### 2. Export with asc

By default, `asc xcode export` generates App Store Connect export options with automatic signing. It uses a local export destination unless `--wait` is set, in which case it uses direct upload:

```bash
asc xcode export \
  --archive-path ".asc/artifacts/App.xcarchive" \
  --ipa-path ".asc/artifacts/App.ipa" \
  --xcodebuild-flag=-allowProvisioningUpdates \
  --output json
```

Generate a plist separately when it needs review, reuse, or manual signing:

```bash
asc xcode export-options generate \
  --archive-path ".asc/artifacts/App.xcarchive" \
  --output-path ".asc/ExportOptions.plist" \
  --output json
```

For manual signing, add `--signing-style manual` and optionally `--team-id "TEAM_ID"`. Existing files require `--overwrite`.

To upload directly through Xcode and wait for App Store Connect processing, omit `--export-options` and add `--wait`:

```bash
asc xcode export \
  --archive-path ".asc/artifacts/App.xcarchive" \
  --ipa-path ".asc/artifacts/App.ipa" \
  --wait \
  --output json
```

### 3. Upload or publish

Upload an exported IPA:

```bash
asc builds upload --app "APP_ID" --ipa ".asc/artifacts/App.ipa" --wait
```

Distribute to TestFlight:

```bash
asc publish testflight --app "APP_ID" --ipa ".asc/artifacts/App.ipa" --group "GROUP_ID" --wait
```

Publish to the App Store:

```bash
asc publish appstore --app "APP_ID" --ipa ".asc/artifacts/App.ipa" --version "1.2.3" --wait
asc publish appstore --app "APP_ID" --ipa ".asc/artifacts/App.ipa" --version "1.2.3" --wait --submit --confirm
```

## macOS App Store flow

Archive with the helper:

```bash
asc xcode archive \
  --project "MacApp.xcodeproj" \
  --scheme "MacApp" \
  --configuration Release \
  --clean \
  --archive-path ".asc/artifacts/MacApp.xcarchive" \
  --xcodebuild-flag=-destination \
  --xcodebuild-flag=generic/platform=macOS \
  --output json
```

If your macOS export produces a `.pkg`, use Xcode export with your `ExportOptions.plist`, then upload the package:

```bash
xcodebuild -exportArchive \
  -archivePath ".asc/artifacts/MacApp.xcarchive" \
  -exportPath ".asc/artifacts/MacAppExport" \
  -exportOptionsPlist "ExportOptions.plist" \
  -allowProvisioningUpdates

asc builds upload \
  --app "APP_ID" \
  --pkg ".asc/artifacts/MacAppExport/MacApp.pkg" \
  --version "1.0.0" \
  --build-number "123" \
  --wait
```

For `.pkg` uploads, `--version` and `--build-number` are required because they are not auto-extracted like IPA metadata.

## Raw xcodebuild fallback

Use raw `xcodebuild` only when neither `asc xcode archive --help` nor
`asc xcode export --help` covers a project-specific option. Prefer passing
extra arguments through `--xcodebuild-flag` first.

```bash
xcodebuild -showBuildSettings -scheme "App"
```

## Troubleshooting

### No profiles for bundle ID during export

- Add `--xcodebuild-flag=-allowProvisioningUpdates` to `asc xcode export`.
- Verify the Apple ID is logged into Xcode.
- Verify profiles with the `asc-signing-setup` skill.

### CFBundleVersion too low

```bash
asc xcode version edit --next-build-number --app "APP_ID" --platform IOS
```

Then rebuild and upload again.

### Build rejected for missing macOS icon

macOS requires ICNS icons with all required sizes. Fix the asset catalog, rebuild, then export/upload again.

## Notes

- Prefer `asc xcode archive` and `asc xcode export` for deterministic local artifacts.
- Use `--overwrite` only when replacing existing local artifacts intentionally.
- Use `--wait` on upload/publish paths when the next step depends on processed builds.
- For submission readiness, use `asc-submission-health`.

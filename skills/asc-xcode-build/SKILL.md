---
name: asc-xcode-build
description: Build, archive, export, upload, and manage Xcode version/build numbers with the current asc xcode helpers before App Store Connect upload or submission. Use when creating an IPA or PKG for upload.
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
asc xcode version bump --type build
asc xcode version bump --type patch
```

Use `--project-dir "./MyApp"` when not running from the project root. Use `--project "./MyApp/App.xcodeproj"` when the directory contains multiple projects. Use `--target "App"` for deterministic reads in multi-target projects.

To avoid low build-number rejects, resolve a remote-safe build number first:

```bash
asc builds next-build-number --app "APP_ID" --version "1.2.3" --platform IOS --output json
asc xcode version edit --build-number "NEXT_BUILD"
```

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

```bash
asc xcode export \
  --archive-path ".asc/artifacts/App.xcarchive" \
  --export-options "ExportOptions.plist" \
  --ipa-path ".asc/artifacts/App.ipa" \
  --xcodebuild-flag=-allowProvisioningUpdates \
  --output json
```

If `ExportOptions.plist` uses direct App Store Connect upload, add `--wait` to poll for build discovery and processing:

```bash
asc xcode export \
  --archive-path ".asc/artifacts/App.xcarchive" \
  --export-options "UploadExportOptions.plist" \
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
asc builds next-build-number --app "APP_ID" --version "1.2.3" --platform IOS
asc xcode version edit --build-number "NEXT_BUILD"
```

Then rebuild and upload again.

### Build rejected for missing macOS icon

macOS requires ICNS icons with all required sizes. Fix the asset catalog, rebuild, then export/upload again.

## Notes

- Prefer `asc xcode archive` and `asc xcode export` for deterministic local artifacts.
- Use `--overwrite` only when replacing existing local artifacts intentionally.
- Use `--wait` on upload/publish paths when the next step depends on processed builds.
- For submission readiness, use `asc-submission-health`.

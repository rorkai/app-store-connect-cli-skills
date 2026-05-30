---
name: asc-signing-setup
description: Set up bundle IDs, capabilities, signing certificates, provisioning profiles, and encrypted signing sync with the asc cli. Use when onboarding a new app, rotating signing assets, or sharing them across a team.
---

# asc signing setup

Use this skill when you need to create or renew signing assets for iOS/macOS apps.

## Preconditions
- Auth is configured (`asc auth login` or `ASC_*` env vars).
- You know the bundle identifier and target platform.
- You have a CSR file for certificate creation, or you will let `asc certificates create --generate-csr` create one.

## Workflow
1. Create or find the bundle ID:
   - `asc bundle-ids list --paginate`
   - `asc bundle-ids create --identifier "com.example.app" --name "Example" --platform IOS`
2. Configure bundle ID capabilities:
   - `asc bundle-ids capabilities list --bundle "BUNDLE_ID"`
   - `asc bundle-ids capabilities add --bundle "BUNDLE_ID" --capability ICLOUD`
   - Add capability settings when required:
     - `--settings '[{"key":"ICLOUD_VERSION","options":[{"key":"XCODE_13","enabled":true}]}]'`
3. Create a signing certificate:
   - `asc certificates list --certificate-type IOS_DISTRIBUTION`
   - `asc certificates create --certificate-type IOS_DISTRIBUTION --csr "./cert.csr"`
   - Or generate a key and CSR inline:
     - `asc certificates create --certificate-type IOS_DISTRIBUTION --generate-csr --key-out "./signing/dist.key" --csr-out "./signing/dist.csr"`
4. Create a provisioning profile:
   - `asc profiles create --name "AppStore Profile" --profile-type IOS_APP_STORE --bundle "BUNDLE_ID" --certificate "CERT_ID"`
   - Include devices for development/ad-hoc:
     - `asc profiles create --name "Dev Profile" --profile-type IOS_APP_DEVELOPMENT --bundle "BUNDLE_ID" --certificate "CERT_ID" --device "DEVICE_ID"`
5. Download the profile:
   - `asc profiles download --id "PROFILE_ID" --output "./profiles/AppStore.mobileprovision"`
6. Inspect and install the downloaded profile locally when needed:
   - `asc profiles inspect --path "./profiles/AppStore.mobileprovision" --output table`
   - `asc profiles inspect --path "./profiles/AppStore.mobileprovision" --entitlements --output markdown`
   - `asc profiles local install --path "./profiles/AppStore.mobileprovision"`
   - `asc profiles local list --output table`

## Rotation and cleanup
- Revoke old certificates:
  - `asc certificates revoke --id "CERT_ID" --confirm`
- Delete old profiles:
  - `asc profiles delete --id "PROFILE_ID" --confirm`
- Clean local Xcode provisioning profiles:
  - `asc profiles local clean --expired --dry-run`
  - `asc profiles local clean --expired --confirm`

## Shared team storage with `asc signing sync`
Use this when you want a lightweight, non-interactive alternative to fastlane match for encrypted git-backed certificate/profile storage.

```bash
# Push current ASC signing assets into an encrypted git repo
asc signing sync push \
  --bundle-id "com.example.app" \
  --profile-type IOS_APP_STORE \
  --repo "git@github.com:team/certs.git" \
  --password "$MATCH_PASSWORD"

# Pull and decrypt them into a local directory
asc signing sync pull \
  --repo "git@github.com:team/certs.git" \
  --password "$MATCH_PASSWORD" \
  --output-dir "./signing"
```

Notes:
- `--password` falls back to `ASC_MATCH_PASSWORD`.
- The encrypted repo follows a familiar match-style git layout for certs and profiles.
- `pull` writes files to disk; keychain import or profile installation is a separate step.

## Notes
- Always check `--help` for the exact enum values (certificate types, profile types).
- Use `--paginate` for large accounts.
- `--certificate` accepts comma-separated IDs when multiple certificates are required.
- Device management uses `asc devices` commands (UDID required).
- `asc profiles inspect` and `asc profiles local ...` operate on local disk state, not App Store Connect API resources.

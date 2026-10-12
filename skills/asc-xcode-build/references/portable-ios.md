# Portable iOS compilation and packaging

Use this path for a prepared xtool Swift package with an installed compatible
Swift/Apple SDK toolchain, `xtool`, and `rcodesign`. It does not build arbitrary
Xcode projects or install tools. Review generated package configuration and
resources after any project conversion. See the [CLI portable-build guide](https://github.com/rorkai/App-Store-Connect-CLI/blob/main/docs/linux-ios.md)
for toolchain setup, SDK constraints, and licensing notes.

The supported device artifact is one thin arm64 iOS app plus resources. Nested
executables, frameworks, extensions, watch apps, App Clips, dylibs, and app symlinks
are rejected. Prefer the Xcode workflow when the project needs those features.

```bash
asc builds compile --package-path "./AppPackage" --product "App" --platform device --configuration release --app-path "./artifacts/App.app" --output json
asc builds package --app-path "./artifacts/App.app" --ipa-path "./artifacts/App.ipa" --identity "./signing/App.p12" --identity-password-file "./secrets/password" --provisioning-profile "./signing/App.mobileprovision" --entitlements "./signing/entitlements.plist" --output json
```

Pin a compatible xtool/SDK pair: xtool can rebuild an outdated installed SDK.
Serialize compilation within each prepared package. Output paths must be new;
inspect an incomplete publication before retrying. Compiler and signer logs go
to stderr; receipts go to stdout.

Signing inputs are explicit local files. Protect the identity and password file
with owner-only permissions; the password file contains one line. The profile
must match the exact app bundle ID and certificate and authorize the requested
entitlements. Omission of `--entitlements` does not inherit optional capabilities.
Use `asc-signing-setup` for separately authorized provisioning work.

`--ad-hoc` is local test signing, not registered-device distribution: its IPA is
not accepted by Apple or installable on an ordinary iPhone. Simulator compilation
uses `--platform simulator` and still needs a Mac simulator host to run; it cannot
be packaged as a device IPA.

Device compilation reports unknown signing type. Packaging reports
`signatureVerified: false` and `appleAcceptance: notVerified`; successful local
packaging is not proof of Apple acceptance. Upload or publish the genuinely signed
IPA only when that next stage is authorized, using the existing upload/release
workflow. These portable commands do not discover credentials, provision, or upload.

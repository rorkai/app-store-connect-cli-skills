---
name: asc-release-flow
description: Orchestrate App Store releases with asc, including staging a version, uploading or building an artifact, publishing, and submitting for review. Use when the user wants to prepare or execute a release. Keep Game Center item preparation in this skill; route other readiness failures, stuck submissions, cancellation, and retry decisions to asc-submission-health.
---

# App Store release orchestration

Use this skill to carry a release from an approved plan to App Store review. Keep Game Center item preparation here; keep other blocker diagnosis and review recovery in `asc-submission-health`.

## Ownership boundary

This skill owns:

- staging metadata and attaching a build;
- publishing an IPA or building locally;
- submitting a prepared version;
- assembling a multi-item review submission.

Use [references/multi-item-submissions.md](references/multi-item-submissions.md) for Game Center item preparation or attachment blockers. Stop and use `asc-submission-health` for other validation blockers, a stuck submission, cancellation, or retry decisions.

## Preconditions

- Resolve `APP_ID`, the version string, `VERSION_ID` when needed, and `BUILD_ID` when a build already exists.
- Configure auth with `asc auth login` or `ASC_*` environment variables.
- Confirm the intended platform. Use `IOS` unless the app targets another platform.
- Keep canonical metadata in `./metadata` when the workflow applies metadata.
- Require a dry run before a mutating high-level command, then require `--confirm` for submission.

## Choose the release lane

| Intent | Command |
| --- | --- |
| Prepare metadata and attach an existing build without submitting | `asc release stage` |
| Submit an already prepared version | `asc review submit` |
| Upload an IPA or build locally, then optionally submit | `asc publish appstore` |
| Submit the app version with IAP, subscription, or Game Center version items | lower-level `asc review` submission commands |

Do not mix lanes after one has already created a review submission. Inspect the existing submission first and continue through the matching lower-level commands.

## Run the readiness gate

Validate before any submission:

```bash
asc validate --app "APP_ID" --version "1.2.3" --platform IOS --output table
```

Use strict mode when warnings must stop automation:

```bash
asc validate --app "APP_ID" --version "1.2.3" --platform IOS --strict --output table
```

If the app includes digital goods, use `asc-submission-health` to verify those resources before returning to this flow. If it includes Game Center items, continue with [references/multi-item-submissions.md](references/multi-item-submissions.md), which owns their preparation and attachment.

If validation reports a Game Center item blocker, stop and use [references/multi-item-submissions.md](references/multi-item-submissions.md). For every other blocker, stop the release flow and use `asc-submission-health`. Do not bury unrelated remediation inside the release run.

## Stage an existing build

Use `asc release stage` to ensure the version, apply or copy metadata, attach the selected build, and run validation without creating a review submission.

Preview metadata-driven staging:

```bash
asc release stage \
  --app "APP_ID" \
  --version "1.2.3" \
  --build "BUILD_ID" \
  --metadata-dir "./metadata/version/1.2.3" \
  --dry-run \
  --output table
```

Apply the reviewed plan:

```bash
asc release stage \
  --app "APP_ID" \
  --version "1.2.3" \
  --build "BUILD_ID" \
  --metadata-dir "./metadata/version/1.2.3" \
  --confirm
```

Use `--copy-metadata-from "1.2.2"` instead of `--metadata-dir` when carrying localization metadata forward. Add `--strict-validate` when warnings should fail the stage.

## Submit a prepared version

Use `asc review submit` after metadata, review details, availability, build processing, and product readiness are already resolved.

```bash
asc review submit --app "APP_ID" --version "1.2.3" --build "BUILD_ID" --dry-run --output table
asc review submit --app "APP_ID" --version "1.2.3" --build "BUILD_ID" --confirm
```

Use `--version-id "VERSION_ID"` instead of `--version` when the exact version ID is known. `--build` may be omitted only when the intended build is already attached and verified.

## Upload or build, then publish

Use `asc publish appstore` when the release starts from an IPA or a local Xcode project/workspace.

Preview an IPA upload and submission:

```bash
asc publish appstore \
  --app "APP_ID" \
  --ipa "./App.ipa" \
  --version "1.2.3" \
  --submit \
  --dry-run \
  --output table
```

Run it after reviewing the plan:

```bash
asc publish appstore \
  --app "APP_ID" \
  --ipa "./App.ipa" \
  --version "1.2.3" \
  --submit \
  --wait \
  --confirm
```

For local-build mode, provide `--workspace` or `--project` with `--scheme` instead of `--ipa`. Use `--metadata-dir` when the publish command should apply canonical version metadata after ensuring the version.

Omit `--submit` when the user wants upload and attachment only.

## Submit multiple review items

Read [references/multi-item-submissions.md](references/multi-item-submissions.md) when the app version must ship with versioned IAP, subscription, subscription-group, or Game Center items. Add only items the user has resolved and inspected.

## Handoff after submission

Report:

- the app, version, platform, build, and submission IDs;
- which lane ran and whether it completed;
- every mutation confirmed by the user;
- the exact command to monitor the resulting submission.

Use `asc-submission-health` for monitoring, cancellation, rejection diagnosis, or retry decisions.

## Guardrails

- Do not use removed `submit-preflight`, `submit-create`, or `release-run` shortcuts.
- Do not add `--confirm` until the dry-run plan matches the requested release.
- Do not create a second review submission when one already exists for the version.
- Do not turn a validation failure into a partial release; stop at the failing gate.
- Keep data on stdout and diagnostics on stderr when wrapping commands in automation.

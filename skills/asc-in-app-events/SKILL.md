---
name: asc-in-app-events
description: Create and localize App Store in-app events, upload event media, and submit or recover event review submissions with asc. Use when managing in-app events, event card or details page assets, or event-specific submission errors.
---

# asc in-app events

Use `asc app-events` for the requested stages only. A localization, media upload,
or diagnostic request does not authorize creating or submitting another event.
Preserve the resolved app, event, platform, locales, and existing authorization.

## Inspect the target

Check `asc app-events --help` and the relevant subcommand help before execution.
Resolve the app ID and auth profile; inspect an existing event before changing it:

```bash
asc app-events list --app "APP_ID" --paginate --output json
asc app-events view --event-id "EVENT_ID" --output json
asc app-events localizations list --event-id "EVENT_ID" --paginate --output json
```

Use explicit `--output json` when parsing results; output defaults are TTY-aware.
Keep event IDs and localization IDs distinct.

## Prepare and create

- Choose the event badge and intended territories. Check help for accepted
  `--event-type`, `--purpose`, and `--purchase-requirement` values; do not infer
  that every value described in App Store Connect is supported by the CLI.
- Set future RFC 3339 dates: start before end, duration from 15 minutes to 31 days,
  and publish start no more than 14 days before the event and no later than start.
  The CLI parses timestamps but does not enforce all of Apple's schedule rules.
- Provide a deep link that opens the event's destination. Test the universal link
  or custom URL scheme in the intended app build; a registered scheme alone does
  not prove the destination works. Creation without a deep link can succeed even
  though the event is not ready for review.

Replace the date variables with the agreed schedule before creating:

```bash
asc app-events create \
  --app "APP_ID" --name "Summer Challenge" --event-type CHALLENGE \
  --start "$START_RFC3339" --end "$END_RFC3339" \
  --publish-start "$PUBLISH_START_RFC3339" \
  --deep-link "myapp://event/summer" --primary-locale en-US \
  --purchase-requirement NO_COST_ASSOCIATED \
  --priority NORMAL --purpose APPROPRIATE_FOR_ALL_USERS --output json
```

`--name` is the internal reference name, limited to 64 characters. Retain the
returned event ID. For an existing event, use `asc app-events update` instead of
creating a replacement; check its help for the fields being changed.

## Localize and upload media

Create only missing, requested localizations. Displayed names allow 30 characters,
short descriptions 50, and long descriptions 120. Use
`asc app-events localizations update --localization-id "LOC_ID"` for an existing
localization, supplying the text flags that need changing.

```bash
asc app-events localizations create \
  --event-id "EVENT_ID" --locale en-US --name "Summer Challenge" \
  --short-description "Win three duels a day." \
  --long-description "Play every day during the challenge to earn the summer badge."

asc app-events screenshots create \
  --event-id "EVENT_ID" --locale en-US \
  --path "./event-card.png" --asset-type EVENT_CARD
asc app-events screenshots create \
  --event-id "EVENT_ID" --locale en-US \
  --path "./event-details.png" --asset-type EVENT_DETAILS_PAGE
```

Use `--localization-id "LOC_ID"` instead of `--event-id` plus `--locale` when
the localization is already resolved. Video uploads use
`asc app-events video-clips create`; inspect its help for asset types and
`--preview-frame-time-code`.

To reuse existing Asset Library media, use `asc app-events localizations placements`
with the event localization ID and `EVENT_CARD_ASSET` or `EVENT_DETAILS_PAGE_ASSET`.
Follow the [Asset Library workflow](../asc-metadata-sync/references/asset-library.md)
for upload, delivery, and placement checks; a placement does not submit the event.

Use JPG/JPEG/PNG images, at most 500 MB each. Export opaque images without
alpha channels for upload compatibility. Apple specifies these dimensions:

| Asset | Aspect ratio | Minimum | Maximum |
| --- | --- | --- | --- |
| `EVENT_CARD` | 16:9 | 1920 × 1080 | 3840 × 2160 |
| `EVENT_DETAILS_PAGE` | 9:16 | 1080 × 1920 | 2160 × 3840 |

Avoid embedded text or logos where possible. Account for crops, gradients, and
App Store controls; inspect the App Store Connect preview when available rather
than assuming a fixed percentage of the image is safe. Verify media for each
intended localization; do not assume a locale with translated text inherits
missing assets from the primary locale. See Apple's [media specifications](https://developer.apple.com/help/app-store-connect/reference/in-app-events/in-app-event-media-and-audio-specifications/)
and [presentation guidance](https://developer.apple.com/app-store/in-app-events/).

## Verify and submit

Read back the schedule, deep link, localized text, and delivered media. Inspect
video clips too when used. Report any preview or link behavior not verified.

```bash
asc app-events view --event-id "EVENT_ID" --output json
asc app-events screenshots list --event-id "EVENT_ID" --locale en-US --paginate --output json
```

For an app with an approved iOS version, when submission is authorized and no
existing submission needs to be continued:

```bash
asc app-events submit --event-id "EVENT_ID" --app "APP_ID" --platform IOS --confirm --output json
asc review submissions-get --id "SUBMISSION_ID" --output json
```

Use the `submissionId` from the receipt for the second command. Report the state
returned by Apple; a successful submit receipt is not evidence of approval or
publication. If the app has no approved iOS version, Apple requires the event in
the first version's submission. Use `asc-release-flow` to prepare that version,
then add the event to its intended draft with `review items-add` as shown below;
skip the standalone `app-events submit` command. Coordinate the build and event
release when new functionality is needed. See Apple's [submission guidance](https://developer.apple.com/help/app-store-connect/manage-submissions-to-app-review/submit-an-in-app-event).

## Recover without duplicating work

`app-events submit` creates a new review submission, adds the event, then submits
it. A failure after creation can leave a draft behind, even when no submission ID
appears in the error. Inspect submissions and their items before retrying:

```bash
asc review submissions-list --app "APP_ID" --platform IOS --paginate --output json
asc review submissions-get --id "SUBMISSION_ID" --output json
asc review items-list --submission "SUBMISSION_ID" --paginate --output json
```

For an intended `READY_FOR_REVIEW` draft, confirm the app, platform, and all items
belong to the authorized submission. Repair the event first. For example, use
`asc app-events update --event-id "EVENT_ID" --deep-link "myapp://event/summer"`
when Apple reports a missing deep link. Then reuse the draft:

```bash
asc review items-add --submission "SUBMISSION_ID" --item-type appEvents --item-id "EVENT_ID" --if-exists skip
asc review submissions-submit --id "SUBMISSION_ID" --confirm
```

Do not cancel an empty `READY_FOR_REVIEW` draft: it has no active review to cancel.
Do not resubmit a submission already waiting for review. Route other submission
states to `asc-submission-health`, preserving the target and authorized work.

A `403 FORBIDDEN_ERROR` can indicate real access restrictions. Check the selected
profile, app access, and role before diagnosing a transient service error; one
403 is not a reason to rotate credentials or assume they are valid. If recent
successful calls support a transient diagnosis, retry reads with bounded backoff
and stop if the error persists. Before repeating an uncertain create or upload,
list the existing resource and inspect its delivery state to avoid duplicates.

For current provider requirements, consult Apple's [event setup guidance](https://developer.apple.com/help/app-store-connect/offer-in-app-events/offer-in-app-events/).

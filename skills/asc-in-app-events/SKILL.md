---
name: asc-in-app-events
description: Create, localize, illustrate, and submit App Store in-app events with asc app-events, and avoid the review and media pitfalls that the API does not report up front. Use when the user wants to publish an in-app event, upload event card or details page art, localize an event, or work out why an event cannot be submitted.
---

# asc in-app events

Use this skill to take an in-app event from nothing to "Waiting for Review" with
`asc app-events`, and to check the things App Store Connect only complains about
at submission time.

## Preconditions
- Auth configured (`asc auth login` or `ASC_*` env vars).
- Know your app ID (`ASC_APP_ID` or `--app`).
- The live build of the app can open a deep link (custom URL scheme or universal
  link). See "Deep link" below; without one the event cannot be reviewed.

## Workflow

1. Preflight the deep link and the art (sections below).
2. Create the event.
3. Add one localization per locale you support.
4. Upload media to the primary locale.
5. Verify, then submit.

### 1. Create the event

```bash
asc app-events create \
  --app "APP_ID" \
  --name "Summer Challenge" \
  --event-type CHALLENGE \
  --start "2026-06-01T00:00:00Z" \
  --end "2026-06-30T23:59:59Z" \
  --publish-start "2026-05-25T00:00:00Z" \
  --deep-link "myapp://event/summer" \
  --purchase-requirement NO_COST_ASSOCIATED \
  --primary-locale en-US \
  --priority NORMAL \
  --purpose APPROPRIATE_FOR_ALL_USERS \
  --output json
```

- `--name` is the reference name. It is not shown on the App Store.
- `--event-type` is the badge: `LIVE_EVENT`, `PREMIERE`, `CHALLENGE`,
  `COMPETITION`, `NEW_SEASON`, `MAJOR_UPDATE`, `SPECIAL_EVENT`.
- `--purpose`: `APPROPRIATE_FOR_ALL_USERS`, `ATTRACT_NEW_USERS`,
  `KEEP_ACTIVE_USERS_INFORMED`, `BRING_BACK_LAPSED_USERS`.
- `--priority`: `HIGH` or `NORMAL`.
- Run `asc app-events create --help` for the purchase requirement values the
  installed CLI accepts.

Keep the returned event ID.

### 2. Localize

```bash
asc app-events localizations create \
  --event-id "EVENT_ID" \
  --locale "en-US" \
  --name "Summer Challenge" \
  --short-description "Win three duels a day." \
  --long-description "Play every day in June to earn the summer badge."

asc app-events localizations list --event-id "EVENT_ID" --output table
```

Update an existing one with
`asc app-events localizations update --localization-id "LOC_ID" ...`.

### 3. Upload media

Each localization takes an event card and an event details page:

```bash
asc app-events screenshots create \
  --event-id "EVENT_ID" --locale "en-US" \
  --path "./event-card.png" --asset-type EVENT_CARD

asc app-events screenshots create \
  --event-id "EVENT_ID" --locale "en-US" \
  --path "./event-details.png" --asset-type EVENT_DETAILS_PAGE
```

Video works the same way through `asc app-events video-clips create`, with
`--preview-frame-time-code` for the poster frame.

### 4. Verify and submit

```bash
asc app-events view --event-id "EVENT_ID" --output json
asc app-events screenshots list --event-id "EVENT_ID" --locale "en-US" --output table
asc app-events submit --event-id "EVENT_ID" --app "APP_ID" --confirm
```

Do not run `submit` until the user has seen the art in the App Store Connect
preview (see "Media safe area").

## Pitfalls

These are field observations from shipping events, not documented API rules.
Treat them as checks to run, and re-verify when behaviour looks different.

### Deep link: creating works, review does not

`asc app-events create` succeeds without `--deep-link`, so the gap stays hidden
until the end. Adding the event to a review submission then fails with:

```
409 ENTITY_ERROR.ATTRIBUTE.REQUIRED  deepLink
```

With `asc app-events submit` it surfaces as
`app-events submit: failed to add event to submission`. The review submission
created a moment earlier can be left behind empty: inspect it with
`asc review submissions-get --id "SUBMISSION_ID"` and cancel it with
`asc submit cancel --id "SUBMISSION_ID" --confirm` before trying again.

Before creating the event:

- Confirm the app registers a URL scheme (`CFBundleURLTypes` in `Info.plist`) or
  an associated domain for universal links.
- Confirm the build that is live on the App Store handles that link. If the app
  has no scheme at all, a new build has to ship first; the event cannot be
  reviewed before it.

If the event already exists, fix it in place:

```bash
asc app-events update --event-id "EVENT_ID" --deep-link "myapp://event/summer"
```

### Media safe area: keep the story in the top half

The App Store draws the badge, the event name and the short description over
the lower part of the art, on a blur that starts at roughly 55% of the height.
That applies to both assets:

| Asset | Size | Covered by the store |
|---|---|---|
| `EVENT_CARD` | 1920 x 1080 | lower ~45% (badge, name, short description) |
| `EVENT_DETAILS_PAGE` | 1080 x 1920 | lower ~45%, plus the app icon top-left and the close button top-right |

Rules for the art:

- Put everything that tells the story in the top ~52% of the frame.
- Leave the top-left and top-right corners of the details page empty.
- Avoid text in the art, above all the event name or the app name: the store
  prints both next to it already.
- Check the result in the App Store Connect preview before submitting. A layout
  that looks balanced as a flat image often loses its subject under the blur.

### Media per locale: upload once, to the primary locale

When the art carries no text, upload it to the primary locale only. The other
localizations fall back to it.

Uploading a copy to every locale multiplies the calls (two assets times every
locale, per event) and has triggered bursts of:

```
403 FORBIDDEN_ERROR  The API key in use does not allow this request
```

on event screenshots and event localizations, for reads as well as writes,
while the hourly quota was far from used up. The key is fine and the role is
fine: the error clears by itself within minutes.

- Do not rotate the key or change its role in response to this error.
- Retry reads and updates with backoff.
- Do not blindly retry an upload: list first
  (`asc app-events screenshots list --event-id "EVENT_ID" --locale "en-US"`) so a
  retried `create` does not leave a duplicate asset.

Upload per locale only when the art really differs by language.

### Events and a version in the same release

An event submitted with `asc app-events submit` goes into its own review
submission. If the event depends on something in a new build (the deep link
handler, or the feature the event advertises), make sure that build is approved
and live before the event's `--publish-start`, or the event will point at an
app that cannot open it.

## Checklist before submit

- [ ] `deepLink` is set, and the live build opens it.
- [ ] Start, end and publish start are RFC 3339, and publish start is not after start.
- [ ] Every supported locale has a name and a short description.
- [ ] `EVENT_CARD` and `EVENT_DETAILS_PAGE` exist on the primary locale.
- [ ] The subject of the art sits in the top ~52%; details page corners are empty.
- [ ] The user has looked at the App Store Connect preview.

## Notes

- Default output is JSON; use `--output table` for a quick human check.
- Deleting needs `--confirm`: `asc app-events delete --event-id "EVENT_ID" --confirm`.
- Always check `asc app-events --help` and the subcommand `--help` for the flags
  of the installed CLI version.

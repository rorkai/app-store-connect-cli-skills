# Asset Library media and placements

Use this workflow for reusable media, including product-page headers, search
creative assets, screenshots, previews, and event artwork. Uploading, assigning,
submitting for review, and publishing are separate operations; perform only the
requested stages and preserve the app, locale, platform, and authorization.

## Inspect and upload

```bash
asc asset-library view --app "APP_ID" --output json
asc asset-library specs --output json
asc asset-library images list --library-id "LIBRARY_ID" --paginate --output json
asc asset-library videos list --library-id "LIBRARY_ID" --paginate --output json
```

Inspect existing media before uploading a duplicate. List commands support
category, state, specification, reference-name, and ID filters; check leaf help.
Upload defaults to `CREATIVE_ASSETS` for headers, search, and event media. Select
`APP_SCREENSHOTS_AND_PREVIEWS` for in-use screenshots and app previews.

```bash
asc asset-library images upload --library-id "LIBRARY_ID" --file "./header.png" --output json
asc asset-library videos upload --library-id "LIBRARY_ID" --file "./preview.mp4" --category APP_SCREENSHOTS_AND_PREVIEWS --output json
```

Use current specifications for the selected category; images cannot contain an
alpha channel, and videos require `ffprobe`. Save the asset ID, including from
partial failure receipts. Inspect `images view --id` or `videos view --id` before
retrying a timeout: processing may still continue. A processed upload is not
App Review approval.

## Assign media to a localization

Use the localization resource ID, not the parent version, page, or event ID.
Inspect placements first; create does not remove an existing assignment.

```bash
asc localizations placements list --localization-id "LOC_ID" --include image,video --paginate --output json
asc localizations placements create --localization-id "LOC_ID" --image-id "IMAGE_ID" --placement-type PRODUCT_PAGE_HEADER_ASSET
asc localizations placements create --localization-id "LOC_ID" --video-id "VIDEO_ID" --placement-type APP_PREVIEW --placement-group IPHONE_DUO_PROFILE
```

Supply exactly one image or video ID. Screenshots need images; previews need
videos and an explicit device placement group. Header/search creative assets use
`DEFAULT_PROFILE`. CPP and PPO placements live under `product-pages custom-pages
localizations placements` and `product-pages experiments treatments localizations
placements`; inspect their own help rather than substituting parent IDs.

Event placements use `app-events localizations placements` and accept only
`EVENT_CARD_ASSET` or `EVENT_DETAILS_PAGE_ASSET`. Event reordering is unsupported.
Use `swap --confirm` for an authorized replacement; a failed swap does not justify
deleting the previous placement. Read back the intended localization afterward.

Placement deletion retains library media. Library archive/delete and video poster
changes can affect multiple uses; inspect asset `placements` before changing them.
Deleting multiple placements is not atomic, so inspect partial receipts before retrying.

## Review and publication

For a first app version, include assets with that version's submission using the
[multi-item release flow](../../asc-release-flow/references/multi-item-submissions.md).
Standalone asset review requires an approved app version: inspect and reuse the
intended draft before creating one, then attach `appAssetLibraryImages` or
`appAssetLibraryVideos` through `review items-add`. Inspect all items before an
authorized `review submissions-submit --confirm`. Assets already in active
submissions must not be attached to a second submission.

Read back asset and submission states. An upload, an `ACTIVE` placement, or a swap
receipt does not prove approval or storefront publication. The CLI has no separate
public placement-publication command. See the [CLI Asset Library guide](https://github.com/rorkai/App-Store-Connect-CLI/blob/main/guides/asset-library.mdx)
for the full lifecycle and known provider-verification limits.

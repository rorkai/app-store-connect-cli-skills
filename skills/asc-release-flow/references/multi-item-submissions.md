# Multi-item review submissions

Read this reference when one review submission must contain the app version plus versioned digital goods, Game Center components, or both.

Follow only the section for the current phase:

- During readiness, complete **Prepare every item**, then return to the main release flow.
- Enter **Assemble the submission** only after the app version is staged and the multi-item lane is selected.
- Enter **Submit** only after inspecting the assembled draft and obtaining confirmation.

## Prepare every item

- Resolve the exact `VERSION_ID` and each product or component version ID.
- Use `asc-submission-health` to repair missing IAP, subscription, or subscription-group versions.
- Confirm the Game Center app version exists:

```bash
asc game-center app-versions list --app "APP_ID" --output table
asc game-center app-versions create --app-store-version-id "VERSION_ID" --output json
```

Create only when the intended Game Center app version is absent.

## Assemble the submission

Do not create a review submission from the readiness gate. Start this phase only after the app version and build are staged and the user has selected the multi-item lane.

Create one review submission and capture its ID:

```bash
asc review submissions-create --app "APP_ID" --platform IOS --output json
```

Add the app version first, followed by the resolved product and Game Center version items:

```bash
asc review items add --submission "SUBMISSION_ID" --item-type appStoreVersions --item-id "VERSION_ID"
asc review items add --submission "SUBMISSION_ID" --item-type inAppPurchaseVersions --item-id "IAP_VERSION_ID"
asc review items add --submission "SUBMISSION_ID" --item-type subscriptionVersions --item-id "SUBSCRIPTION_VERSION_ID"
asc review items add --submission "SUBMISSION_ID" --item-type subscriptionGroupVersions --item-id "GROUP_VERSION_ID"
asc review items add --submission "SUBMISSION_ID" --item-type gameCenterLeaderboardVersions --item-id "GC_LEADERBOARD_VERSION_ID"
```

Supported Game Center item types also include:

- `gameCenterAchievementVersions`
- `gameCenterActivityVersions`
- `gameCenterChallengeVersions`
- `gameCenterLeaderboardSetVersions`

Add only types required for this release. Do not submit placeholder or unresolved IDs.

## Submit

Inspect the assembled submission before the final mutation, then require confirmation:

```bash
asc review submissions-get --id "SUBMISSION_ID" --include items --output table
asc review items list --submission "SUBMISSION_ID" --paginate --output table
asc review submissions-submit --id "SUBMISSION_ID" --confirm
```

If inspection shows an existing active or completed submission instead of the draft being assembled, stop and diagnose through `asc-submission-health` rather than creating another submission.

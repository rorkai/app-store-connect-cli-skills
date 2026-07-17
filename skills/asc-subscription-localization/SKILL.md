---
name: asc-subscription-localization
description: Bulk-localize subscription, subscription-group, and in-app purchase display names across App Store locales using asc, including API 4.4.1 version-scoped v2 resources. Use when filling or updating subscription/IAP names and descriptions without App Store Connect UI work.
---

# asc subscription localization

Use this skill to bulk-create or bulk-update display names (and descriptions) for subscriptions, subscription groups, and in-app purchases across all App Store Connect locales. This eliminates the tedious manual process of clicking through each language in App Store Connect to set the same display name.

## Preconditions
- Auth configured (`asc auth login` or `ASC_*` env vars).
- Know your app ID (`ASC_APP_ID` or `--app`).
- Subscription groups and subscriptions already exist.

## Choose the API scope first

API 4.4.1 adds discrete versions for IAPs, subscriptions, and subscription
groups. A version ID is different from its product, subscription, or group ID.

- Use `asc ... versions localizations ...` when the localization belongs to a
  version and must participate in that version's review lifecycle.
- Use the existing `asc subscriptions localizations`,
  `asc subscriptions groups localizations`, and `asc iap localizations`
  commands only for the stable v1 product- or group-scoped resources.
- Never pass a product, subscription, or group ID to a version-scoped command.

Resolve or create versions before localizing them:

```bash
asc iap versions list --iap-id "IAP_ID" --paginate --output table
asc subscriptions versions list --subscription-id "SUB_ID" --paginate --output table
asc subscriptions groups versions list --group-id "GROUP_ID" --paginate --output table
```

Create a version only when the requested review lifecycle needs a new one:

```bash
asc iap versions create --iap-id "IAP_ID"
asc subscriptions versions create --subscription-id "SUB_ID"
asc subscriptions groups versions create --group-id "GROUP_ID"
```

## Supported App Store Locales

These are the locales supported by App Store Connect for subscription and IAP localizations:

```
ar-SA, ca, cs, da, de-DE, el, en-AU, en-CA, en-GB, en-US,
es-ES, es-MX, fi, fr-CA, fr-FR, he, hi, hr, hu, id, it,
ja, ko, ms, nl-NL, no, pl, pt-BR, pt-PT, ro, ru, sk,
sv, th, tr, uk, vi, zh-Hans, zh-Hant
```

## Workflow: Bulk-localize a subscription version (v2)

List existing localizations, create only missing locales, then verify:

```bash
asc subscriptions versions localizations list --version-id "VERSION_ID" --paginate --output table
asc subscriptions versions localizations create --version-id "VERSION_ID" --locale "LOCALE" --name "Display Name" --description "Description"
asc subscriptions versions localizations list --version-id "VERSION_ID" --paginate --output table
```

Updates distinguish omitted values, strings (including an empty string), and
JSON `null`:

```bash
asc subscriptions versions localizations update --id "LOC_ID" --name "New Name" --description ""
asc subscriptions versions localizations update --id "LOC_ID" --clear-description
```

Do not combine a value flag with its matching `--clear-name` or
`--clear-description` flag.

## Workflow: Bulk-localize a subscription group version (v2)

```bash
asc subscriptions groups versions localizations list --version-id "VERSION_ID" --paginate --output table
asc subscriptions groups versions localizations create --version-id "VERSION_ID" --locale "LOCALE" --name "Group Display Name" --custom-app-name "My App"
asc subscriptions groups versions localizations update --id "LOC_ID" --clear-custom-app-name
asc subscriptions groups versions localizations list --version-id "VERSION_ID" --paginate --output table
```

Use `--clear-name` or `--clear-custom-app-name` only when JSON `null` is
intended; omission leaves the attribute unchanged.

## Workflow: Bulk-localize an IAP version (v2)

```bash
asc iap versions localizations list --version-id "VERSION_ID" --paginate --output table
asc iap versions localizations create --version-id "VERSION_ID" --locale "LOCALE" --name "Display Name" --description "Description"
asc iap versions localizations update --localization-id "LOC_ID" --clear-description
asc iap versions localizations list --version-id "VERSION_ID" --paginate --output table
```

## Legacy v1 workflow: Bulk-Localize a Subscription

### 1. Resolve IDs

```bash
# Find subscription groups
asc subscriptions groups list --app "APP_ID" --paginate --output table

# Find subscriptions within a group
asc subscriptions list --group-id "GROUP_ID" --paginate --output table
```

### 2. Check existing localizations

```bash
asc subscriptions localizations list --subscription-id "SUB_ID" --paginate --output table
```

This shows which locales already have a name set. Only create localizations for missing locales.

### 3. Create localizations for all missing locales

For each locale that does not already have a localization, run:

```bash
asc subscriptions localizations create \
  --subscription-id "SUB_ID" \
  --locale "LOCALE" \
  --name "Display Name"
```

For example, to set "Monthly Pro" across all locales:

```bash
# One command per locale (skip any that already exist)
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "ar-SA" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "ca" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "cs" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "da" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "de-DE" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "el" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "en-AU" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "en-CA" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "en-GB" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "es-ES" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "es-MX" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "fi" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "fr-CA" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "fr-FR" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "he" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "hi" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "hr" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "hu" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "id" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "it" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "ja" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "ko" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "ms" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "nl-NL" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "no" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "pl" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "pt-BR" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "pt-PT" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "ro" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "ru" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "sk" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "sv" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "th" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "tr" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "uk" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "vi" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "zh-Hans" --name "Monthly Pro"
asc subscriptions localizations create --subscription-id "SUB_ID" --locale "zh-Hant" --name "Monthly Pro"
```

### 4. Verify

```bash
asc subscriptions localizations list --subscription-id "SUB_ID" --paginate --output table
```

## Legacy v1 workflow: Bulk-Localize a Subscription Group

Subscription groups also have their own display name per locale (this is the "group name" shown to users in the subscription management sheet).

### 1. Check existing group localizations

```bash
asc subscriptions groups localizations list --group-id "GROUP_ID" --paginate --output table
```

### 2. Create for missing locales

```bash
asc subscriptions groups localizations create \
  --group-id "GROUP_ID" \
  --locale "LOCALE" \
  --name "Group Display Name"
```

Optional: set a custom app name for the group:

```bash
asc subscriptions groups localizations create \
  --group-id "GROUP_ID" \
  --locale "LOCALE" \
  --name "Group Display Name" \
  --custom-app-name "My App"
```

### 3. Verify

```bash
asc subscriptions groups localizations list --group-id "GROUP_ID" --paginate --output table
```

## Legacy v1 workflow: Bulk-Localize an In-App Purchase

IAPs have their own localization commands with the same pattern.

### 1. Resolve IAP ID

```bash
asc iap list --app "APP_ID" --output table
```

### 2. Check existing localizations

```bash
asc iap localizations list --iap-id "IAP_ID" --paginate --output table
```

### 3. Create for missing locales

```bash
asc iap localizations create \
  --iap-id "IAP_ID" \
  --locale "LOCALE" \
  --name "Display Name"
```

Optional description:

```bash
asc iap localizations create \
  --iap-id "IAP_ID" \
  --locale "LOCALE" \
  --name "Unlock All Features" \
  --description "One-time purchase to unlock all premium features"
```

### 4. Verify

```bash
asc iap localizations list --iap-id "IAP_ID" --paginate --output table
```

## Updating Existing Localizations

To change the display name for existing localizations:

### Subscriptions
```bash
asc subscriptions localizations update --id "LOC_ID" --name "New Name"
```

### Subscription Groups
```bash
asc subscriptions groups localizations update --id "LOC_ID" --name "New Group Name"
```

### In-App Purchases
```bash
asc iap localizations update --localization-id "LOC_ID" --name "New Name"
```

To bulk-update, list existing localizations first, extract the IDs, then update each one.

## Bulk-Localize All Subscriptions in an App

For a full app with multiple subscription groups and subscriptions:

```bash
# 1. List all groups
asc subscriptions groups list --app "APP_ID" --paginate

# 2. For each group, localize the group itself
#    (repeat group localization workflow above)

# 3. For each group, list subscriptions
asc subscriptions list --group-id "GROUP_ID" --paginate

# 4. For each subscription, localize it
#    (repeat subscription localization workflow above)
```

## Agent Behavior

- Resolve whether the target is version-scoped v2 or legacy v1 before listing
  or mutating localizations.
- Keep version IDs separate from product, subscription, and group IDs.
- Always list existing localizations first to avoid duplicate creation errors.
- Skip locales that already have a localization; only create missing ones.
- When the user provides a single display name, use it for all locales (same name everywhere).
- When the user provides translated names per locale, use the locale-specific name for each.
- If a description is provided, pass `--description` on create. Otherwise omit it.
- Use `--output table` for verification steps so the user can visually confirm.
- Use explicit `--output json` for intermediate automation steps; output
  defaults are TTY-aware.
- After bulk creation, always run the list command to verify completeness.
- For apps with many subscriptions, process them sequentially per group to keep output readable.
- If a create call fails for a locale, log the locale and error, then continue with the remaining locales. After the batch completes, report all failures together so the user can address them.

## Notes
- Subscription display names are what users see on the subscription management sheet and in purchase dialogs.
- Creating a localization for a locale that already exists will fail; always check first.
- There is no bulk API; each locale requires a separate create call.
- Use `--paginate` on list commands to ensure all existing localizations are returned.
- Use the `asc-id-resolver` skill if you only have app names instead of IDs.

---
name: asc-ppp-pricing
description: Set territory-specific pricing for subscriptions and in-app purchases using current asc setup, pricing summary, price import, and price schedule commands. Use when adjusting prices by country or implementing localized PPP strategies.
---

# PPP pricing (per-territory pricing)

Use this skill to create or update localized pricing across territories based on purchasing power parity (PPP) or your own regional pricing strategy.

Prefer the current high-level flows:
- `asc subscriptions setup` and `asc iap setup` when you are creating a new product
- `asc subscriptions pricing ...` for subscription pricing changes
- `asc iap pricing summary` and `asc iap pricing schedules ...` for IAP pricing changes

## Preconditions
- Ensure credentials are set (`asc auth login` or `ASC_*` env vars).
- Prefer `ASC_APP_ID` or pass `--app` explicitly.
- Decide your base territory (usually `USA`) and baseline price.
- Use `asc pricing territories list --paginate` if you need supported territory IDs.

## Subscription PPP workflow

### New subscription: bootstrap with `setup`
Use `setup` when you are creating a new subscription and want one verified flow for the group, localizations, App Review screenshot, complete equalized price matrix, and sale availability. The sale territories remain an independently selected subset of the full price matrix.

```bash
asc subscriptions setup \
  --app "APP_ID" \
  --group-reference-name "Pro" \
  --reference-name "Pro Monthly" \
  --product-id "com.example.pro.monthly" \
  --subscription-period ONE_MONTH \
  --locale "en-US" \
  --display-name "Pro Monthly" \
  --description "Unlock everything" \
  --price "9.99" \
  --price-territory "USA" \
  --territories "USA,CAN,GBR" \
  --output json
```

Notes:
- `setup` materializes Apple's complete equalized price matrix from the selected base price, then verifies the final state by default.
- Use `--no-verify` only when you explicitly want speed over readback verification.
- Use `--tier` or `--price-point-id` instead of `--price` when your workflow is tier-driven.
- If an existing subscription remains `MISSING_METADATA` with the same selected base price, re-run the setup inputs with `--repair` to atomically rebuild and re-save the matrix.

### Inspect current subscription pricing before changes
Use the summary view first when you want a compact current-state snapshot.

```bash
asc subscriptions pricing summary --subscription-id "SUB_ID" --territory "USA"
asc subscriptions pricing summary --subscription-id "SUB_ID" --territory "IND"
asc subscriptions pricing prices list --subscription-id "SUB_ID" --paginate
```

Use `summary` for quick before/after spot checks and `prices list` when you need raw price records.

### Preferred bulk PPP update: import a CSV with dry run
For broad PPP rollouts, prefer the subscription pricing import command instead of manually adding territory prices one by one.

Example CSV:

```csv
territory,price,start_date,preserved
IND,2.99,2026-04-01,false
BRA,4.99,2026-04-01,false
MEX,4.99,2026-04-01,false
DEU,8.99,2026-04-01,false
```

Dry-run first:

```bash
asc subscriptions pricing prices import \
  --subscription-id "SUB_ID" \
  --input "./ppp-prices.csv" \
  --dry-run \
  --output table
```

Apply for real:

```bash
asc subscriptions pricing prices import \
  --subscription-id "SUB_ID" \
  --input "./ppp-prices.csv" \
  --output table
```

Notes:
- `--dry-run` validates rows and resolves price points without creating prices.
- `--continue-on-error=false` gives you a fail-fast mode.
- CSV required columns: `territory`, `price`
- CSV optional columns: `currency_code`, `start_date`, `preserved`, `preserve_current_price`, `price_point_id`
- When `price_point_id` is omitted, the CLI resolves the matching price point for the row's territory and price automatically.
- Territory inputs in import can be 3-letter IDs, 2-letter codes, or common territory names that map cleanly.

### One-off subscription territory changes
For a small number of manual overrides, use the canonical `set` command.

```bash
asc subscriptions pricing prices set --subscription-id "SUB_ID" --price "2.99" --territory "IND"
asc subscriptions pricing prices set --subscription-id "SUB_ID" --tier 5 --territory "BRA"
asc subscriptions pricing prices set --subscription-id "SUB_ID" --price-point "PRICE_POINT_ID" --territory "DEU"
```

Notes:
- Add `--start-date "YYYY-MM-DD"` to schedule a future change.
- Add `--preserved` when you want to preserve the current price relationship.
- The command handles both initial pricing and later price changes.

### Discover raw price points only when you need them
Use price-point lookup and equalizations when you want to inspect Apple's localized ladder directly or pin exact price point IDs.

```bash
asc subscriptions pricing price-points list --subscription-id "SUB_ID" --territory "USA" --paginate --price "9.99"
asc subscriptions pricing price-points equalizations --price-point-id "PRICE_POINT_ID" --paginate
```

### Verify after apply
Re-run the summary and raw list views after changes.

```bash
asc subscriptions pricing summary --subscription-id "SUB_ID" --territory "IND"
asc subscriptions pricing summary --subscription-id "SUB_ID" --territory "BRA"
asc subscriptions pricing prices list --subscription-id "SUB_ID" --paginate
```

If the subscription was newly created, you can also use `asc subscriptions setup` with verification enabled instead of stitching together separate create and pricing steps.

### Subscription availability
If you need to explicitly enable territories for an existing subscription, use the pricing availability family.

```bash
asc subscriptions pricing availability edit --subscription-id "SUB_ID" --territories "USA,CAN,IND,BRA"
asc subscriptions pricing availability view --subscription-id "SUB_ID"
```

## IAP PPP workflow

### New IAP: bootstrap with `setup`
Use `setup` when you are creating a new IAP and want to create the product, first localization, and initial price schedule in one verified flow.

```bash
asc iap setup \
  --app "APP_ID" \
  --type NON_CONSUMABLE \
  --reference-name "Pro Lifetime" \
  --product-id "com.example.pro.lifetime" \
  --locale "en-US" \
  --display-name "Pro Lifetime" \
  --description "Unlock everything forever" \
  --price "9.99" \
  --base-territory "USA" \
  --output json
```

Notes:
- `setup` verifies the created IAP, localization, and price schedule by default.
- Use `--start-date` for scheduled pricing.
- Use `--tier` or `--price-point-id` when you want deterministic tier- or ID-based setup.

### Inspect current IAP pricing before changes
Use `asc iap pricing summary` as the main current-state summary for PPP work.

```bash
asc iap pricing summary --iap-id "IAP_ID" --territory "USA"
asc iap pricing summary --iap-id "IAP_ID" --territory "IND"
```

This returns the base territory, current price, estimated proceeds, and scheduled changes for the requested territory.

### Discover candidate IAP price points
Use price-point lookup when you want to inspect or pin exact price point IDs.

```bash
asc iap pricing price-points list --iap-id "IAP_ID" --territory "USA" --paginate --price "9.99"
asc iap pricing price-points equalizations --id "PRICE_POINT_ID"
```

### Create or update an IAP price schedule
For manual PPP updates, create a price schedule directly.

```bash
asc iap pricing schedules create --iap-id "IAP_ID" --base-territory "USA" --price "4.99" --start-date "2026-04-01"
asc iap pricing schedules create --iap-id "IAP_ID" --base-territory "USA" --tier 5 --start-date "2026-04-01"
asc iap pricing schedules create --iap-id "IAP_ID" --base-territory "USA" --prices "PRICE_POINT_ID:2026-04-01"
```

Use these when you are intentionally creating or replacing schedule entries. For deeper inspection:

```bash
asc iap pricing schedules view --iap-id "IAP_ID"
asc iap pricing schedules manual-prices --schedule-id "SCHEDULE_ID" --paginate
asc iap pricing schedules automatic-prices --schedule-id "SCHEDULE_ID" --paginate
```

### Verify after apply
Use the summary command again after scheduling or applying pricing changes.

```bash
asc iap pricing summary --iap-id "IAP_ID" --territory "USA"
asc iap pricing summary --iap-id "IAP_ID" --territory "IND"
```

For future-dated schedules, expect scheduled changes rather than an immediately updated current price.

## Common PPP strategy patterns

### Base territory first
- Pick one baseline territory, usually `USA`.
- Set the baseline price there first.
- Derive lower or higher territory targets from that baseline.

### Tiered regional pricing
- High-income markets stay close to baseline.
- Mid-income markets get moderate discounts.
- Lower-income markets get stronger PPP adjustments.

### Spreadsheet-driven rollout
- Build the target territory list in a CSV.
- Dry-run the import.
- Fix any resolution failures.
- Apply the import.
- Re-run summary checks for the most important territories.

## Notes
- Prefer canonical commands in docs and automation: `asc subscriptions pricing ...`
- `asc subscriptions pricing ...` is the supported subscription pricing family; do not use the removed `asc subscriptions prices ...` path.
- Prefer canonical IAP commands in docs and automation: `asc iap pricing ...`
- `asc subscriptions pricing prices import --dry-run` is the safest subscription batch PPP path today.
- `asc subscriptions setup` and `asc iap setup` already provide built-in post-create verification.
- There is not yet a single first-class before/after PPP diff command; use the current summary commands before and after apply.
- Price changes may take time to propagate in App Store Connect and storefronts.

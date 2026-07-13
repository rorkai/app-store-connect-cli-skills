---
name: asc-revenuecat-catalog-sync
description: Reconcile App Store Connect subscriptions and in-app purchases with RevenueCat products, entitlements, offerings, and packages using asc and RevenueCat MCP. Use when setting up or syncing subscription catalogs across ASC and RevenueCat.
---

# asc RevenueCat catalog sync

Use this skill to keep App Store Connect (ASC) and RevenueCat aligned, including creating missing ASC items and mapping them to RevenueCat resources.

## When to use
- You want to bootstrap RevenueCat from an existing ASC catalog.
- You want to create missing ASC subscriptions/IAPs, then map them into RevenueCat.
- You need a drift audit before release.
- You want deterministic product mapping based on identifiers.

## Preconditions
- `asc` authentication is configured (`asc auth login` or `ASC_*` env vars).
- RevenueCat MCP server is configured and authenticated.
- In Cursor and VS Code, OAuth auth is available for RevenueCat MCP. API key auth is also supported.
- You know:
  - ASC app ID (`APP_ID`)
  - RevenueCat `project_id`
  - target RevenueCat app type (`app_store` or `mac_app_store`) and bundle ID for create flows
- Use a write-enabled RevenueCat API v2 key when applying changes.

## Safety defaults
- Start in **audit mode** (read-only).
- Require explicit confirmation before writes.
- Never delete resources in this workflow.
- Continue on per-item failures and report all failures at the end.

## Canonical identifiers
- Primary cross-system key: ASC `productId` == RevenueCat `store_identifier`.
- Keep `productId` stable once products are live.
- Do not use display names as unique identifiers.

## Scope boundary
- RevenueCat MCP configures RevenueCat resources; it does not create App Store Connect products directly.
- Use `asc` commands to create missing ASC subscription groups, subscriptions, and IAPs before RevenueCat mapping.

## Modes

### 1) Audit mode (default)
1. Read ASC source catalog.
2. Read RevenueCat target catalog.
3. Build a diff with actions:
   - missing in ASC
   - missing in RevenueCat
   - mapping conflicts (identifier/type/app mismatch)
4. Present a plan and wait for confirmation.

### 2) Apply mode (explicit)
Execute approved actions in this order:
1. Ensure ASC groups/subscriptions/IAP exist.
2. Ensure RevenueCat app/products exist.
3. Ensure entitlements and product attachments.
4. Ensure offerings/packages and package attachments.
5. Verify and print a final reconciliation summary.

## Step-by-step workflow

### Step A - Read current ASC catalog

```bash
asc subscriptions groups list --app "APP_ID" --paginate --output json
asc iap list --app "APP_ID" --paginate --output json
# for each subscription group:
asc subscriptions list --group-id "GROUP_ID" --paginate --output json
```

### Step B - Read current RevenueCat catalog (MCP)

Use these MCP tools (with `project_id` and pagination where applicable):
- `mcp_RC_get_project`
- `mcp_RC_list_apps`
- `mcp_RC_list_products`
- `mcp_RC_list_entitlements`
- `mcp_RC_list_offerings`
- `mcp_RC_list_packages`

### Step C - Build mapping plan

Map ASC product types to RevenueCat product types:
- ASC subscription -> RevenueCat `subscription`
- ASC IAP `CONSUMABLE` -> RevenueCat `consumable`
- ASC IAP `NON_CONSUMABLE` -> RevenueCat `non_consumable`
- ASC IAP `NON_RENEWING_SUBSCRIPTION` -> RevenueCat `non_renewing_subscription`

Suggested entitlement policy:
- subscriptions: one entitlement per subscription group (or explicit map provided by user)
- non-consumable IAP: one entitlement per product
- consumable IAP: no entitlement by default unless user asks

### Step D - Ensure missing ASC items (if requested)

Create or complete ASC resources first, then re-read ASC to capture canonical
IDs. A RevenueCat product mapping is not proof that the corresponding ASC
subscription is review-ready.

```bash
# create subscription group
asc subscriptions groups create --app "APP_ID" --reference-name "Premium"

# create or converge a review-ready subscription in one workflow
asc subscriptions setup \
  --app "APP_ID" \
  --group-reference-name "Premium" \
  --group-locale "en-US" \
  --group-display-name "Premium" \
  --reference-name "Monthly" \
  --product-id "com.example.premium.monthly" \
  --subscription-period ONE_MONTH \
  --locale "en-US" \
  --display-name "Premium Monthly" \
  --description "Unlock all premium features." \
  --review-screenshot "./review.png" \
  --price "3.99" \
  --price-territory "USA" \
  --territories "USA"

# create iap
asc iap create \
  --app "APP_ID" \
  --type NON_CONSUMABLE \
  --ref-name "Lifetime" \
  --product-id "com.example.lifetime"
```

`subscriptions setup` must finish the ASC metadata that RevenueCat cannot:
group localization, subscription localization, App Review screenshot delivery,
the complete App Store price matrix, and sale availability. Keep sale
availability scoped to the requested territories; pricing still needs Apple's
complete equalized territory matrix.

If an existing API-created subscription remains `MISSING_METADATA` even though
the selected base price is unchanged, re-run the same setup inputs with
`--repair`. Repair atomically rebuilds and re-saves the complete equalized price
matrix; it is not a duplicate single-price POST.

After every ASC subscription create, update, or repair, require this final gate
before creating or attaching the RevenueCat subscription product:

```bash
asc validate subscriptions --app "APP_ID" --output json --pretty
```

After every ASC IAP create or update, require the IAP gate in strict mode so
warnings also block the RevenueCat product mapping:

```bash
asc validate iap --app "APP_ID" --strict --output json --pretty
```

Do not treat setup as successful if Apple still reports `MISSING_METADATA`, the
review screenshot is not `COMPLETE`, or the validator reports incomplete or
unverified pricing coverage. Do not attach an IAP while its strict validator
reports warnings or errors. Preserve both validator JSON outputs in the final
audit evidence.

### Step E - Ensure RevenueCat app and products

Use MCP:
- create app if missing: `mcp_RC_create_app`
- create products: `mcp_RC_create_product`
  - `store_identifier` = ASC `productId`
  - `app_id` = RevenueCat app ID
  - `type` from mapping above

### Step F - Ensure entitlements and attachments

Use MCP:
- list/create entitlements: `mcp_RC_list_entitlements`, `mcp_RC_create_entitlement`
- attach products: `mcp_RC_attach_products_to_entitlement`
- verify attachments: `mcp_RC_get_products_from_entitlement`

### Step G - Ensure offerings and packages (optional)

Use MCP:
- list/create/update offerings:
  - `mcp_RC_list_offerings`
  - `mcp_RC_create_offering`
  - `mcp_RC_update_offering` (`is_current=true` only if requested)
- list/create packages:
  - `mcp_RC_list_packages`
  - `mcp_RC_create_package`
- attach products to packages:
  - `mcp_RC_attach_products_to_package` with `eligibility_criteria: "all"`

Recommended package keys:
- `ONE_WEEK` -> `$rc_weekly`
- `ONE_MONTH` -> `$rc_monthly`
- `TWO_MONTHS` -> `$rc_two_month`
- `THREE_MONTHS` -> `$rc_three_month`
- `SIX_MONTHS` -> `$rc_six_month`
- `ONE_YEAR` -> `$rc_annual`
- lifetime IAP -> `$rc_lifetime`
- custom -> `$rc_custom_<name>`

## Expected output format

Return a final summary with:
- ASC created counts (groups/subscriptions/IAP)
- RevenueCat created counts (apps/products/entitlements/offerings/packages)
- attachment counts (entitlement-products, package-products)
- skipped existing items
- failed items with actionable errors

Example:

```text
ASC: created groups=1 subscriptions=2 iap=1, skipped=14, failed=0
RC: created apps=0 products=3 entitlements=2 offerings=1 packages=2, skipped=27, failed=1
Attachments: entitlement_products=3 package_products=2
Failures:
- com.example.premium.annual: duplicate store_identifier exists on another RC app
```

## Agent behavior
- Always run audit first, even in apply mode.
- Ask for confirmation before create/update operations.
- Match by `store_identifier` first.
- Use full pagination (`--paginate` for ASC, `starting_after` for RevenueCat tools).
- Continue processing after per-item failures and report all failures together.
- Never auto-delete ASC or RevenueCat resources in this skill.
- After ASC subscription writes, run `asc validate subscriptions --app "APP_ID" --output json --pretty` and block RevenueCat attachment for subscriptions with unresolved ASC blockers.
- After ASC IAP writes, run `asc validate iap --app "APP_ID" --strict --output json --pretty` and block RevenueCat attachment if it exits non-zero.

## Common pitfalls
- Wrong RevenueCat `project_id` or app ID.
- Creating RC products under the wrong platform app.
- Accidentally assigning consumables to entitlements.
- Skipping the post-create ASC re-read step.
- Mapping a RevenueCat product before ASC setup finishes localization, review screenshot delivery, the complete price matrix, and availability.
- Missing offering/package verification after product creation.

## Additional resources
- Workflow examples: [examples.md](examples.md)
- Source references: [references.md](references.md)

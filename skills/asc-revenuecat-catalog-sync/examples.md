# Examples: asc RevenueCat catalog sync

Use these examples as execution templates for realistic catalog synchronization workflows.

## Example 1: Drift audit only (read-only)

Goal: compare ASC and RevenueCat, produce a no-write reconciliation report.

### User request
`Audit my ASC subscriptions and IAP catalog against RevenueCat and show what is missing on either side.`

### Expected behavior
1. Read ASC:
   - `asc subscriptions groups list --app "APP_ID" --paginate --output json`
   - `asc iap list --app "APP_ID" --paginate --output json`
   - `asc subscriptions list --group-id "GROUP_ID" --paginate --output json` (for each group)
2. Read RevenueCat via MCP:
   - list apps/products/entitlements/offerings/packages for `project_id`
3. Build and present a diff:
   - missing in ASC
   - missing in RevenueCat
   - type mismatch
   - app/platform mismatch
4. Stop for confirmation (no writes).

## Example 2: Create missing ASC subscriptions, then map to RevenueCat

Goal: bootstrap both systems when store products are partially missing.

### User request
`Ensure monthly and annual subscriptions exist in ASC for app APP_ID, then sync them to RevenueCat project PROJECT_ID under my iOS app.`

### Expected behavior
1. Audit both catalogs, present the no-write plan, and request confirmation.
2. Resolve the ASC parents by exact identifiers with fully paginated reads:
   - `asc subscriptions groups list --app "APP_ID" --paginate --output json`
   - `asc subscriptions list --group-id "GROUP_ID" --paginate --output json`
   - zero exact matches means create, one means reuse its ID, and more than one
     means stop for an explicit ID. Follow [Step D](SKILL.md#step-d---ensure-missing-asc-items-if-requested)
     for every parent and mutable version; never create another resource to
     resolve ambiguity.
3. For a missing subscription, use setup to reconcile its review screenshot,
   complete price matrix, and requested sale availability before version
   metadata. Repeat with the annual product ID and `ONE_YEAR`:

   ```bash
   asc subscriptions setup \
     --app "APP_ID" \
     --group-id "GROUP_ID" \
     --reference-name "Monthly" \
     --product-id "com.example.premium.monthly" \
     --subscription-period ONE_MONTH \
     --review-screenshot "./review.png" \
     --price "3.99" \
     --price-territory "USA" \
     --territories "USA" \
     --no-verify \
     --output json
   ```

   Reuse an existing subscription unless the user explicitly approves its
   reconciliation. Use `--repair` only when the same setup inputs must rebuild
   a stale complete price matrix.
4. Resolve zero/one/many `PREPARE_FOR_SUBMISSION` group and subscription
   versions, then create or update their version-scoped localizations as shown
   in Step D. Read back the selected versions and gate all subscriptions before
   any RevenueCat write:

   ```bash
   mkdir -p "./audit"
   asc validate subscriptions --app "APP_ID" --strict --output json --pretty \
     > "./audit/subscriptions-validation.json"
   ```

5. Only after the validator exits zero, apply the confirmed RevenueCat plan:
   - create app if missing (`type: app_store`, same bundle identifier)
   - create products with matching `store_identifier`
   - create entitlement (for example `premium`) and attach products
   - optionally create `default` offering with `$rc_monthly` and `$rc_annual`
6. Re-read both catalogs and return the final summary and failures list.

## Example 3: Sync one-time IAP and keep consumables entitlement-free

Goal: model recommended entitlement behavior by product type.

### User request
`Sync my non-consumable lifetime IAP and consumable coin pack to RevenueCat.`

### Expected behavior
1. Audit both catalogs, confirm product type mapping, present the plan, and
   request confirmation:
   - `NON_CONSUMABLE` -> `non_consumable`
   - `CONSUMABLE` -> `consumable`
2. Resolve each IAP by exact `productId` with
   `asc iap list --app "APP_ID" --paginate --output json`. Zero exact matches
   means create, one means reuse its ID, and more than one means stop for an
   explicit `IAP_ID`. For a missing IAP, create only the parent; repeat with
   `CONSUMABLE` and the coin product ID:

   ```bash
   asc iap create \
     --app "APP_ID" \
     --type NON_CONSUMABLE \
     --ref-name "Lifetime" \
     --product-id "com.example.lifetime" \
     --output json
   ```

3. For every resolved IAP, reconcile pricing and availability, then resolve
   zero/one/many mutable versions and finish version-scoped localization and
   review-image metadata. The create commands are conditional on a zero-match
   read; update or do nothing for an existing match:

   ```bash
   asc iap pricing summary --iap-id "IAP_ID" --output json
   asc iap pricing schedules create --iap-id "IAP_ID" --base-territory "USA" --prices "PRICE_POINT_ID" --output json
   asc iap pricing availability set --iap-id "IAP_ID" --territories "USA" --output json
   asc iap versions list --iap-id "IAP_ID" --state PREPARE_FOR_SUBMISSION --paginate --output json
   asc iap versions create --iap-id "IAP_ID" --output json
   asc iap versions localizations list --version-id "IAP_VERSION_ID" --paginate --output json
   asc iap versions localizations create --version-id "IAP_VERSION_ID" --locale "en-US" --name "Lifetime" --description "Unlock lifetime access." --output json
   asc iap versions images list --version-id "IAP_VERSION_ID" --paginate --output json
   asc iap versions images create --version-id "IAP_VERSION_ID" --file "./review.png" --output json
   ```

4. Gate all resolved IAPs before any RevenueCat creation or attachment:

   ```bash
   mkdir -p "./audit"
   asc validate iap --app "APP_ID" --strict --output json --pretty \
     > "./audit/iap-validation.json"
   ```

5. Only after the validator exits zero, apply the confirmed RevenueCat plan:
   - create both products
   - attach **non-consumable** product to an entitlement (for example `lifetime_access`)
   - skip entitlement attachment for consumable by default (unless user explicitly asks)
6. Re-read both catalogs and return created/skipped/failed counts.

## Example 4: Controlled apply in CI-style automation

Goal: make apply mode safe and repeatable in team workflows.

### User request
`Run a full sync and apply missing resources.`

### Expected behavior
1. Run the fully paginated ASC and RevenueCat audit and print a no-write plan.
2. Request explicit approval before any ASC or RevenueCat create/update.
3. Apply each approved item in deterministic order:
   - resolve ASC parents and mutable versions with the zero/one/many rules in
     Step D
   - reconcile version-scoped metadata, review screenshots/images, pricing,
     and availability
   - save and require a zero exit from `asc validate subscriptions --app "APP_ID" --strict --output json --pretty` and/or `asc validate iap --app "APP_ID" --strict --output json --pretty`
   - RC app/product, but only for items whose applicable ASC gate passed
   - RC entitlement + attachments
   - RC offering/package + attachments
4. Continue after per-item failures, but never map an item whose ASC gate
   failed; aggregate every error.
5. Re-read both systems and print a machine-readable summary plus a
   human-readable recap.

## Suggested natural-language prompts for MCP

- `List all apps in RevenueCat project PROJECT_ID and show which one matches bundle id com.example.app`
- `Create RevenueCat product com.example.premium.monthly as subscription in app APP_ID`
- `Create entitlement premium and attach product PRODUCT_ID`
- `Create offering default with packages $rc_monthly and $rc_annual`
- `Show complete offering configuration including packages and attached products`

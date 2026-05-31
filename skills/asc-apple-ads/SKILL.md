---
name: asc-apple-ads
description: Use when managing Apple Ads with asc, including auth, org lookup, campaigns, ad groups, ads, keywords, reports, raw API calls, and safe live testing.
---

# asc Apple Ads

Use this skill when a task involves Apple Ads or `asc ads`.

## Ground Rules
- Run `asc ads --help` or the specific subgroup help before scripting a command.
- Apple Ads auth is separate from App Store Connect auth. `asc auth login` does not configure `asc ads`.
- Use JSON output for automation: `--output json`.
- Most commands need an org ID. Prefer `--org` for one-off commands and `ASC_ADS_ORG_ID` for a scoped session.
- Never guess payload fields. Use Apple Ads request JSON in a file and pass it with `--file`.
- Do not mutate a live account until the user has named the org and approved the resource type. Prefer read-only checks first.

## Auth

Stored profile:

```bash
asc ads auth login \
  --name "Marketing" \
  --client-id "$ASC_ADS_CLIENT_ID" \
  --team-id "$ASC_ADS_TEAM_ID" \
  --key-id "$ASC_ADS_KEY_ID" \
  --private-key "$ASC_ADS_PRIVATE_KEY_PATH" \
  --org "$ASC_ADS_ORG_ID" \
  --network
```

Environment auth:

```bash
export ASC_ADS_CLIENT_ID="SEARCHADS_CLIENT_ID"
export ASC_ADS_TEAM_ID="SEARCHADS_TEAM_ID"
export ASC_ADS_KEY_ID="KEY_ID"
export ASC_ADS_PRIVATE_KEY_PATH="$HOME/.asc/apple-ads-private-key.pem"
export ASC_ADS_ORG_ID="123456"
```

Short-lived token auth:

```bash
export ASC_ADS_ACCESS_TOKEN="ACCESS_TOKEN"
export ASC_ADS_ORG_ID="123456"
```

Useful checks:

```bash
asc ads auth status --validate --output json
asc ads auth doctor --output json
asc ads me view --output json
asc ads acls --output json
```

## Org Resolution

When the org ID is unknown:

```bash
asc ads acls --output json
```

Use the returned org ID:

```bash
asc ads campaigns --org "123456" --limit 10 --output json
```

Org precedence is `--org`, `ASC_ADS_ORG_ID`, stored profile `org_id`, then config `ads.org_id`.

## Read Workflows

Campaigns and ad groups:

```bash
asc ads campaigns --org "123456" --limit 100 --output json
asc ads campaigns --org "123456" --paginate --output json
asc ads campaigns view --org "123456" --campaign 987654321 --output json
asc ads ad-groups list --org "123456" --campaign 987654321 --output json
```

Discovery:

```bash
asc ads apps search --org "123456" --query "My App" --limit 10 --output json
asc ads product-pages list --org "123456" --adam-id 1234567890 --states VISIBLE --output json
asc ads creatives list --org "123456" --limit 100 --output json
asc ads geo search --org "123456" --query "San Francisco" --country-code US --limit 10 --output json
```

Reports:

```bash
asc ads reports campaigns --org "123456" --file reporting-request.json --output json
asc ads reports keywords --org "123456" --campaign 987654321 --file reporting-request.json --output json
```

Reporting and find endpoints keep pagination in the JSON body.

## Mutating Workflows

Create and update commands take Apple Ads JSON files:

```bash
asc ads campaigns create --org "123456" --file campaign.json --output json
asc ads campaigns update --org "123456" --campaign 987654321 --file campaign-update.json --output json
asc ads ad-groups create --org "123456" --campaign 987654321 --file ad-group.json --output json
```

Bulk endpoints often require arrays:

```bash
asc ads targeting-keywords create-bulk \
  --org "123456" \
  --campaign 987654321 \
  --ad-group 123456789 \
  --file keywords.json \
  --output json
```

Delete commands require `--confirm`:

```bash
asc ads targeting-keywords delete-bulk \
  --org "123456" \
  --campaign 987654321 \
  --ad-group 123456789 \
  --file keyword-ids.json \
  --confirm \
  --output json

asc ads campaigns delete --org "123456" --campaign 987654321 --confirm
```

For live tests, create paused resources with names such as `ASC CLI Live Test <timestamp>`. Clean up only the parent campaign or ad group created for that test. Apple may reject direct deletion for default product page creative ads, but deleting the test parent campaign or ad group can clean up the test resource.

## Raw API

Use raw requests when Apple adds a field before the first-class command surface changes:

```bash
asc ads api request \
  --method POST \
  --path v5/campaigns/find \
  --org "123456" \
  --file selector.json \
  --output json
```

Raw requests accept only Apple Ads v5 paths or `https://api.searchads.apple.com/api/v5/...` URLs. `DELETE` still requires `--confirm`.

## Live Test Checklist

- Start with `asc ads me view --output json` and `asc ads acls --output json`.
- Print the target org ID before mutations.
- Create paused or future-dated resources.
- Use a unique test name.
- Save created IDs from JSON output.
- Delete only the test parent campaign or ad group created during the run.
- Run a final campaigns find/list query to confirm cleanup.

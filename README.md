# asc cli skills

A collection of Agent Skills for shipping with the [asc cli](https://github.com/rorkai/App-Store-Connect-CLI) (`asc`). These skills help agents run builds, TestFlight, metadata, submissions, signing, and Apple Ads workflows.

This is a community-maintained, unofficial skill pack and is not affiliated with Apple.

Skills follow the Agent Skills format.

## Installation

Install the skills with `asc`:

```bash
asc install-skills
```

Or install them directly from GitHub with the Agent Skills installer:

```bash
npx skills add rorkai/app-store-connect-cli-skills
```

### Claude Code plugin

This repository is also a Claude Code marketplace. Add it once, then install the `asc` plugin:

```bash
claude plugin marketplace add rorkai/app-store-connect-cli-skills
claude plugin install asc@rorkai
```

### Codex plugin

The repository includes a Codex plugin manifest and can be listed by a Codex plugin marketplace.
Codex currently installs plugins from configured marketplaces, so use the Agent Skills installer
until `asc` has a public marketplace listing:

```bash
npx skills add rorkai/app-store-connect-cli-skills --agent codex
```

## Available Skills

### asc-cli-usage

Guidance for running `asc` commands (canonical verbs, flags, pagination, output, auth).

**Use when:**
- You need the correct `asc` command or flag combination
- You want JSON-first output and pagination tips for automation
- You need Apple Ads command, auth, org, payload, or pagination guidance

**Example:**

```bash
Find the right asc command to list all builds for app 123456789 as JSON and paginate through everything.
```

### asc-apple-ads

Apple Ads auth, org lookup, campaigns, ad groups, ads, keywords, reports, raw API calls, and safe live testing.

**Use when:**
- You need to read or change Apple Ads resources with `asc ads`
- You need Apple Ads OAuth, profile, or `ASC_ADS_*` guidance
- You need a safe read-first plan before mutating a live Ads account

**Example:**

```bash
Find my Apple Ads org, list campaigns as JSON, and draft a safe plan before creating any test campaign.
```

### asc-workflow

Define and run repo-local automation graphs using `asc workflow` and `.asc/workflow.json`.

**Use when:**
- You are migrating from lane-based automation to repo-local workflows
- You need multi-step orchestration with machine-parseable JSON output for CI/agents
- You need hooks (`before_all`, `after_all`, `error`), conditionals (`if`), and private helper sub-workflows
- You want validation (`asc workflow validate`) with cycle/reference checks before execution

**Example:**

```bash
Create an asc workflow that stages a release, validates it, and only submits when CONFIRM_RELEASE=true.
```

### asc-app-create-ui

Create a new App Store Connect app via browser automation when no API exists.

**Use when:**
- You need to create an app record (name, bundle ID, SKU, primary language)
- You are comfortable logging in to App Store Connect in a real browser

**Example:**

```bash
Create a new App Store Connect app for com.example.myapp with SKU MYAPP123 and primary language English (U.S.).
```

### asc-xcode-build

Build, archive, generate export options, export, and manage Xcode version/build numbers before uploading.

**Use when:**
- You need to create an IPA or PKG for upload
- You're setting up CI/CD build pipelines
- You need to generate or customize ExportOptions.plist
- You're troubleshooting encryption compliance issues

**Example:**

```bash
Archive and export my macOS app as a PKG I can upload to App Store Connect.
```

### asc-shots-pipeline

Agent-first screenshot pipeline using xcodebuild/simctl, AXe, JSON plans, `asc screenshots frame` (experimental), and `asc screenshots upload`.

**Use when:**
- You need a repeatable simulator screenshot automation flow
- You want AXe-based UI driving before capture
- You need a staged pipeline (capture -> frame -> upload)
- You need to discover supported frame devices (`asc screenshots list-frame-devices`)
- You want pinned Koubou guidance for deterministic framing (`koubou==0.18.1`)

**Example:**

```bash
Build my iOS app, capture the home and settings screens in the simulator, frame them, and prepare them for upload.
```

### asc-release-flow

Stage, upload, publish, and submit App Store releases through dry-run and confirmation-oriented orchestration.

**Use when:**
- A prepared app version or artifact needs to be staged, uploaded, or submitted
- You need to choose between `asc release stage`, `asc review submit`, and `asc publish appstore`
- You need to assemble a multi-item submission containing Game Center or digital-goods versions

For readiness failures, blocker diagnosis, monitoring, cancellation, or retry decisions, use `asc-submission-health`.

**Example:**

> Stage version 2.4.0 with the selected build, show the dry-run plan, and submit it after confirmation.

### asc-signing-setup

Bundle IDs, capabilities, certificates, provisioning profiles, and encrypted signing sync.

**Use when:**
- You are onboarding a new app or bundle ID
- You need to create or rotate signing assets

**Example:**

```bash
Set up signing for com.example.app with iCloud enabled, a distribution certificate, and an App Store profile.
```

### asc-id-resolver

Resolve IDs for apps, builds, app and digital-goods versions, groups, and testers.

**Use when:**
- A command requires IDs and you only have names
- You need an API 4.4.1 IAP, subscription, or subscription-group version ID
- You want deterministic outputs for automation

**Example:**

```bash
Resolve the App Store Connect app ID, latest build ID, and TestFlight group IDs for MyApp.
```

### asc-metadata-sync

Metadata and localization sync (including legacy metadata format migration).

**Use when:**
- You are updating App Store metadata or localizations
- You need to validate character limits before upload
- You need to update privacy policy URL or app-level metadata

**Example:**

```bash
Pull my App Store metadata into ./metadata, update the privacy policy URL, and push the changes back safely.
```

### asc-localize-metadata

Translate App Store metadata (description, keywords, what's new, subtitle) to multiple locales using LLM translation prompts and push via `asc`.

**Use when:**
- You want to localize an app's App Store listing from a source locale (usually en-US)
- You need locale-aware keywords (not literal translations) and strict character limit enforcement
- You want a review-before-upload workflow for translations

**Example:**

```bash
Translate my en-US App Store metadata into German, French, and Japanese, then show me the changes before upload.
```

### asc-aso-audit

Run an offline ASO audit on canonical App Store metadata under `./metadata` and surface keyword gaps using Astro MCP.

**Use when:**
- You want to audit subtitle, keywords, description, and what's new fields for waste and formatting issues
- You want keyword-gap analysis against Astro-tracked rankings and competitor terms
- You want follow-up actions that map cleanly to `asc metadata keywords ...`

**Example:**

```bash
Audit ./metadata for ASO problems, then show the highest-value keyword gaps from Astro for my latest version.
```

### asc-whats-new-writer

Generate engaging, localized App Store release notes from git log, bullet points, or free text using canonical metadata under `./metadata`.

**Use when:**
- You want polished What's New copy from rough release inputs
- You want localized release notes across existing locales
- You want a review-before-upload workflow using `asc metadata push` or direct metadata edits

**Example:**

```bash
Turn these release bullet points into polished What's New notes for en-US and localize them across my existing metadata locales.
```

### asc-submission-health

Diagnose submission blockers, route repairs, monitor review state, cancel unhealthy submissions, and decide when to retry.

**Use when:**
- You want to know whether an app can be submitted now
- Validation reports metadata, compliance, digital-goods, availability, or App Privacy blockers
- A version is not in a valid state
- You need to monitor, cancel, repair, or safely retry a submission

For staging, upload, publication, and submission execution, use `asc-release-flow`.

**Example:**

```bash
Validate version 2.4.0, classify every blocker, route the repairs, and tell me whether it is safe to retry.
```

### asc-testflight-orchestration

Beta groups, testers, build distribution, and What to Test notes.

**Use when:**
- You manage multiple TestFlight groups and testers
- You need consistent beta rollout steps

**Example:**

```bash
Export my current TestFlight config, create a new external group, add testers, and attach the latest build.
```

### asc-build-lifecycle

Build processing, latest build resolution, and cleanup.

**Use when:**
- You are waiting on build processing
- You want automated cleanup and retention policies

**Example:**

```bash
Find the latest processed build for app 123456789 and preview expiring all TestFlight builds older than 90 days.
```

### asc-ppp-pricing

Territory-specific pricing using purchasing power parity (PPP).

**Use when:**
- You want different prices for different countries
- You are implementing localized pricing strategies
- You need to adjust prices based on regional purchasing power

**Example:**

```bash
Update my subscription pricing for India, Brazil, and Mexico using a PPP-style rollout and verify the result.
```

### asc-subscription-localization

Bulk-localize subscription and IAP display names across all App Store locales,
including API 4.4.1 version-scoped v2 resources.

**Use when:**
- You want to set the same subscription display name in every language at once
- You need to fill in missing subscription/group/IAP localizations
- You're tired of clicking through each locale in App Store Connect manually

**Example:**

```bash
Set the display name Monthly Pro across all missing locales for this subscription and verify which locales were created.
```

### asc-revenuecat-catalog-sync

Reconcile App Store Connect subscriptions/IAP with RevenueCat products, entitlements, offerings, and packages.

**Use when:**
- You want to sync ASC product catalogs to RevenueCat
- You need to create missing ASC subscriptions/IAPs before mapping them
- You want an audit-first workflow with explicit apply confirmation

**Example:**

```bash
Audit my App Store Connect subscriptions and IAPs against RevenueCat, then create any missing mappings after I approve the plan.
```

### asc-notarization

Archive, export, and notarize macOS apps with Developer ID signing.

**Use when:**
- You need to notarize a macOS app for distribution outside the App Store
- You want the full flow: archive → Developer ID export → zip → notarize → staple
- You're troubleshooting Developer ID signing or trust chain issues

**Example:**

```bash
Archive my macOS app, export it for Developer ID, notarize the ZIP, and staple the result.
```

### asc-crash-triage

Triage TestFlight crashes, beta feedback, and performance diagnostics.

**Use when:**
- You want to review recent TestFlight crash reports
- You need a crash summary grouped by signature, device, and build
- You want to check beta tester feedback and screenshots
- You need performance diagnostics (hangs, disk writes, launches) for a build

**Example:**

```bash
Show me the latest TestFlight crashes and feedback for MyApp, grouped by signature and affected build.
```

### asc-wall-submit

Submit or update an app entry in the App-Store-Connect-CLI Wall of Apps using `asc apps wall submit`.

**Use when:**
- You want to add your app to the Wall of Apps
- You want to update an existing Wall entry
- You want the built-in CLI Wall submission flow

**Example:**

```bash
Submit app 1234567890 to the Wall of Apps using the built-in asc apps wall submit flow.
```

## Usage

Skills are automatically available once installed. The agent will use them when relevant tasks are detected.

## Skill Structure

Each skill contains:
- `SKILL.md` - Instructions for the agent
- `scripts/` - Helper scripts for automation (optional)
- `references/` - Supporting documentation (optional)

## License

MIT

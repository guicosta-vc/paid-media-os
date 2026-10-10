# Paid Media OS

> A generic, agent-installable operating system for safe Meta advertising:
> strategy -> creative hypotheses -> approved assets -> paused campaign build ->
> reporting -> decision -> iteration.

**Created and owned by Gui Costa and Venture Compass.**

Paid Media OS is a clean, generic starter kit for teams that use Claude,
Hermes, ChatGPT Projects, or another capable agent. It turns a marketing request
into durable, reviewable artifacts instead of an untraceable chat sequence.

It is deliberately conservative around external systems: reads are explicit,
creation begins paused, activation needs a separate approval, and budget changes
are never automatic.

## License and commercial use

Paid Media OS is **source-available** under the PolyForm Noncommercial License 1.0.0.
You may study, modify, and redistribute it for permitted noncommercial purposes.
Commercial use, including agency client service, internal business use, hosted
services, or resale, requires a separate written license. See [LICENSE](LICENSE),
[NOTICE](NOTICE), and [Commercial licensing](COMMERCIAL-LICENSE.md).

## What it includes

- Agent skills for intake, the 50-concept creative bank, Meta operations, and reporting decisions.
- A standard-library Python CLI that creates a private workspace, validates artifacts, reads Meta account and insights data, builds paused Meta objects, and records private receipts.
- Templates for Strategy Locks, creative catalogs, campaign manifests, scoped approvals, reports, and decision records.
- Tests and a release scanner designed to catch customer names, vendor references, common credential markers, and non-English source material before publication.

## What it does not do

- It does not guarantee performance, revenue, ROAS, leads, or policy approval.
- It does not create visual assets, edit video, or replace legal/compliance review.
- It does not write to Meta unless an operator supplies an explicit action, matching approval, runtime acknowledgement, and environment-only token.
- It does not autonomously increase budget, activate campaigns, alter tracking, or operate a scheduler.

## Quick start

```bash
python3 scripts/mos.py init --workspace ./workspace/acme-growth
python3 scripts/mos.py validate --workspace ./workspace/acme-growth
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
python3 scripts/check_release.py --release
```

The first validation is expected to fail until you replace every `REPLACE_` value,
complete the Strategy Lock, catalog approved assets, and provide a real private
account scope. The workspace is ignored by Git. It contains account-specific,
potentially sensitive operating artifacts and must remain private.

## Agent installation

### Claude

Copy the folders in `skills/` to the location your Claude environment uses for custom skills, preserving each `SKILL.md` and `references/` directory. Start a new conversation and tell Claude:

```text
Read AGENT_GUIDE.md and skills/marketing-os/SKILL.md. Help me initialize a private Paid Media OS workspace.
```

### Hermes

Copy a selected folder from `skills/` to your profile's skill directory, or keep this repository available and tell Hermes to read the relevant `SKILL.md` before work. Do not install into a shared global folder if it would expose another customer's workspace.

### Other agents

Attach or paste `AGENT_GUIDE.md`, the relevant `skills/*/SKILL.md`, and the linked reference files. The artifacts and CLI are agent-agnostic. See [Agent compatibility](docs/agent-compatibility.md) for platform-specific installation and an offline acceptance check.

## Operating model

Follow the [implementation guide](docs/implementation-guide.md) for company and agency onboarding, tenant isolation, the full 50-SKU process, production handoffs, paused-build approvals, and reporting decisions.

```text
Evidence and Strategy Lock
  -> 50 creative concepts
  -> verifier and 3-5-ad test cell
  -> approved static or video asset catalog
  -> campaign manifest and read-only checks
  -> separate approval to create paused objects
  -> separate approval to activate
  -> complete data snapshot
  -> decision record: keep, kill, remix, defer, or insufficient data
```

### Strategy and claims

Create `strategy-lock.md` from the template. Separate verified facts, assumptions, and prohibited claims. A strategy is not approved merely because an agent wrote it.

### Creative bank and production handoff

Use `skills/creative-bank/SKILL.md`. The bank contains exactly 50 distinct concepts. The first test cell contains **3 to 5** materially distinct hypotheses, not five synonyms. Each selected concept requires an asset record with an approved copy version, asset checksum, rights status, and either `static` or `video` media kind.

Video is supported as an asset type. The OS does not generate or edit video; it requires a verified Meta asset ID in the catalog before an approved campaign manifest can reference it.

### Meta read-only checks and reporting

Keep the token out of files:

```bash
export META_ACCESS_TOKEN='set-this-in-your-private-shell-only'
python3 scripts/mos.py account-check --workspace ./workspace/acme-growth
python3 scripts/mos.py collect --workspace ./workspace/acme-growth --since 2026-01-01 --until 2026-01-07
python3 scripts/mos.py decide --workspace ./workspace/acme-growth --report reports/insights-2026-01-01_2026-01-07.json
```

The report collector stores a sanitized local receipt and the exact reporting window. It does not claim that a platform event is a business outcome.

### Meta writes: deliberate and gated

Prepare `campaign-manifest.json` and a matching record under `approvals/`. The approval must include the SHA-256 digest of the reviewed manifest; any later edit invalidates it. First run validation and inspect the dry run:

```bash
python3 scripts/mos.py validate --workspace ./workspace/acme-growth
python3 scripts/mos.py create-paused --workspace ./workspace/acme-growth --approval approvals/create-paused.json --dry-run
```

Only the operator can make the API call:

```bash
export META_ACCESS_TOKEN='set-this-in-your-private-shell-only'
python3 scripts/mos.py create-paused --workspace ./workspace/acme-growth --approval approvals/create-paused.json --execute --acknowledge I_UNDERSTAND_THIS_CREATES_PAUSED_META_OBJECTS
```

The command rejects active statuses, expired approvals, unmatched account IDs, missing Meta asset IDs, and an absent acknowledgement. It creates each declared object paused and reads it back. If a request is uncertain, do not rerun it: reconcile the returned object IDs in Meta first.

Activation uses `activate` with a separate `ACTIVATE` approval. Budget changes are intentionally outside the write runner: prepare a recommendation and obtain a new, scoped approval before building your own carefully reviewed extension.

## Repository layout

```text
AGENT_GUIDE.md                    Agent rules and operating order
skills/                           Portable skill folders for agents
templates/                        Copyable, non-secret artifacts
scripts/mos.py                    CLI: local state, Meta reads, gated writes
scripts/check_release.py          Release and leakage scanner
tests/                            Offline unit tests
```

## Meta prerequisites

You need a Meta app/token that is valid for the exact intended ad account, with only the scopes and asset tasks needed for the current action. Test the exact `act_<account-id>` with `account-check` before relying on any broad account list.

For writes, each asset must already have a verified Meta asset ID and the exact campaign manifest must declare the desired account, destination, event, budget, creative asset, and paused target status. Meta API fields and review requirements can change; review Meta's current official documentation before a production run.

## Release status

This is a published public starter kit. It contains only generic examples and intentionally excludes customer workspaces, credentials, account identifiers, private reports, and proprietary third-party material.

## Contributing

Keep all contributions original, generic, and English-only. Never submit client workspaces, vendor materials, exported ad data, screenshots with account details, tokens, personal data, or proprietary third-party prompts.

## Testing

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
python3 scripts/check_release.py --release
```

## Ownership

Copyright (c) 2026 Gui Costa and Venture Compass. See `NOTICE`.

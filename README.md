# Paid Media OS

> A generic, agent-installable operating system for safe Meta advertising:
> strategy -> creative hypotheses -> approved assets -> paused campaign build ->
> immutable reporting -> human decision -> iteration.

**Created and owned by Gui Costa and Venture Compass.**

Paid Media OS is a clean, generic starter kit for teams that use Claude, Hermes, ChatGPT Projects, or another capable agent. It turns a marketing request into durable, reviewable artifacts instead of an untraceable chat sequence.

It is deliberately conservative around external systems: reads are explicit, creation begins paused, activation needs a separate approval, and budget changes are never automatic.

## License and commercial use

Paid Media OS is **source-available** under the Business Source License 1.1 (BUSL-1.1).

You may use, configure, modify, and deploy it commercially for your own business or client services, including agency work, consulting, implementation, creative production, and managed campaign services. You may charge for those services.

Until the Change Date, you may not offer Paid Media OS, or a substantially similar derivative, as a **paid** standalone product, template library, skill pack, agent bundle, course, repository, or competing operating system without a separate written license. This restriction concerns selling the operating system itself, not professional services performed with it. See [LICENSE](LICENSE), [NOTICE](NOTICE), [Commercial licensing](COMMERCIAL-LICENSE.md), and [Trademark policy](TRADEMARKS.md).

Each release changes to Apache-2.0 on the Change Date stated in its LICENSE.

## What it includes

- Agent skills for intake, the 50-concept creative bank, Meta operations, and reporting decisions.
- A standard-library Python CLI that creates a private workspace, validates the complete artifact chain, reads Meta account and insights data, builds paused Meta objects, and records durable private receipts.
- Templates for lifecycle gates, Strategy Locks, creative registers, campaign manifests, scoped approvals, reconciliations, reports, and decision records.
- Tests and a release scanner designed to catch staged secrets, customer identifiers, private paths, and superseded licensing before publication.

## What it does not do

- It does not guarantee performance, revenue, ROAS, leads, or policy approval.
- It does not create visual assets, edit video, or replace legal/compliance review.
- It does not write to Meta unless an operator supplies an explicit action, matching approval, runtime acknowledgement, and environment-only token.
- It does not autonomously increase budget, activate campaigns, alter tracking, or operate a scheduler.

## Quick start

Clone or download the complete repository. Do not install only one `skills/` folder if you need to run the operating system; the skills share the CLI, templates, and safety controls.

```bash
python3 scripts/mos.py init --workspace ./workspace/acme-growth
python3 scripts/mos.py validate --workspace ./workspace/acme-growth
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
python3 scripts/check_release.py --release
```

The first validation is expected to fail until you replace every `REPLACE_` value and complete every private gate. The workspace contains account-specific, potentially sensitive operating artifacts and must remain private.

To make a self-contained copy for another local agent environment:

```bash
python3 scripts/mos.py install-bundle --destination /private/path/paid-media-os
```

## Agent installation

### Claude

Make the full repository or portable bundle available in the workspace. Start a new conversation and tell Claude:

```text
Read AGENT_GUIDE.md and skills/marketing-os/SKILL.md. Help me initialize a private Paid Media OS workspace. Do not perform a Meta write.
```

### Hermes

Keep the complete repository or bundle mounted. Tell Hermes to read `AGENT_GUIDE.md` and the relevant `skills/<name>/SKILL.md` before work. If you install a native skill folder into Hermes, retain a path to the complete bundle because the skills share required artifacts.

### Other agents

Attach or paste `AGENT_GUIDE.md`, the relevant `skills/*/SKILL.md`, and the required templates. The artifacts and CLI are agent-agnostic. See [Agent compatibility](docs/agent-compatibility.md) for the portable-installation contract and offline acceptance check.

## Operating model

Follow the [implementation guide](docs/implementation-guide.md) for company and agency onboarding, tenant isolation, the full 50-SKU process, production handoffs, paused-build approvals, and reporting decisions.

```text
Tenant intake and lifecycle gate
  -> Strategy Lock and approved strategy record
  -> 50-concept bank register
  -> approved 3-5-concept test cell
  -> approved production-register records and asset catalog
  -> manifest with exact asset bindings and read-only account check
  -> separate approval to create paused objects
  -> separate approval to activate one exact object
  -> immutable data snapshot and reviewed reconciliation
  -> recommendation: keep, kill, remix, defer, insufficient-data, or blocked
```

### Strategy, creative, and asset gates

`validate` fails closed until all of these private artifacts agree on tenant, account, and Strategy Lock version:

1. `lifecycle-state.json` — the authoritative operational state, completed tenant intake, owner, tracking evidence, no blockers, and `ready-for-paused-build`.
2. `strategy-approval.json` — an unexpired approval for `strategy-lock.md`.
3. `creative-bank-register.json` — exactly 50 uniquely identified concepts, reviewed against the Strategy Lock.
4. `test-selection.json` — exactly 3 to 5 eligible, materially distinct concepts.
5. `production-register.json` — one approved asset handoff per selected concept.
6. `creative-catalog.json` and `campaign-manifest.json` — exact approved asset and Meta payload binding.

The Markdown templates remain the human-readable source records. The JSON gate records make their approval and scope machine-checkable before an external write.

### Meta read-only checks and reporting

Provide runtime credentials through your private environment, then run an exact-account check and collect an immutable reporting window:

```bash
python3 scripts/mos.py account-check --workspace ./workspace/acme-growth
python3 scripts/mos.py collect --workspace ./workspace/acme-growth --since 2026-01-01 --until 2026-01-07
```

A raw report begins with `coverage_status: unknown`. Do not edit it to make it complete. Instead, complete a separate private reconciliation record with the report's SHA-256, scope, method, evidence references, and reviewer, then validate it and write a recommendation:

```bash
python3 scripts/mos.py reconcile --workspace ./workspace/acme-growth --report reports/insights-2026-01-01_2026-01-07.json --reconciliation reports/reconciliation.json
python3 scripts/mos.py decide --workspace ./workspace/acme-growth --report reports/insights-2026-01-01_2026-01-07.json --reconciliation reports/reconciliation.json
```

The report collector stores the exact reporting window. It does not claim that a platform event is a business outcome.

### Meta writes: deliberate and gated

Prepare `campaign-manifest.json` and a matching `approvals/create-paused.json`. The approval must include the SHA-256 digest of the reviewed manifest; any later edit invalidates it. First run validation and inspect the dry run:

```bash
python3 scripts/mos.py validate --workspace ./workspace/acme-growth
python3 scripts/mos.py create-paused --workspace ./workspace/acme-growth --approval approvals/create-paused.json --dry-run
```

Only a human-authorized operator can make the API call. The runtime requires the Meta token in the process environment, `--execute`, and this exact acknowledgement:

```bash
python3 scripts/mos.py create-paused --workspace ./workspace/acme-growth --approval approvals/create-paused.json --execute --acknowledge I_UNDERSTAND_THIS_CREATES_PAUSED_META_OBJECTS
```

The command rejects active statuses, expired approvals, unmatched account IDs, missing gate records, and asset-payload mismatch. It persists a receipt before every POST, records every response, and verifies account scope and paused status before continuing. If a request is uncertain, do not rerun it: reconcile exact objects in Meta first.

Activation uses `activate` with a separate `ACTIVATE` approval bound to one object ID. Budget changes are intentionally outside the write runner.

## Repository layout

```text
AGENT_GUIDE.md                    Agent rules and operating order
skills/                           Agent workflow skills
templates/                        Copyable, non-secret artifacts and machine gates
scripts/mos.py                    CLI: local state, Meta reads, gated writes
scripts/check_release.py          Staged-release and leakage scanner
tests/                            Offline unit tests
```

## Meta prerequisites

You need a Meta app/token valid for the exact intended ad account, with only the scopes and asset tasks needed for the current action. Test the exact `act_<account-id>` with `account-check` before relying on any broad account list.

For writes, each asset must already have verified Meta asset IDs. Static, carousel, and video IDs must appear exactly in the matching creative payload. Meta API fields and review requirements can change; review Meta's current official documentation before a production run.

## Security and feedback

Security-sensitive findings belong in the private channel described in [SECURITY.md](SECURITY.md), not a public issue. External pull requests are not currently accepted; see [CLA.md](CLA.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## Ownership

Copyright (c) 2026 Gui Costa and Venture Compass. See `NOTICE`.

# Agent Guide

Paid Media OS is a generic, artifact-backed workflow. Do not treat it as permission to spend money, publish ads, change tracking, or infer customer facts.

## Installation contract

Keep the complete repository or a bundle created with `python3 scripts/mos.py install-bundle --destination <path>`. A single `skills/<name>` folder is not enough to run the OS because the CLI, templates, safety policy, and operating guide are shared dependencies.

## Required operating order

1. Read `README.md`, `SECURITY.md`, and the relevant skill under `skills/`.
2. Create a private local workspace with `python3 scripts/mos.py init --workspace <private-path>`.
3. Complete the private tenant intake and lifecycle state. The lifecycle gate is authoritative for whether a Meta write is permitted.
4. Complete and approve `strategy-lock.md`; record the matching version in `strategy-approval.json`.
5. Build exactly 50 concepts only after the Strategy Lock is approved; record them in `creative-bank-register.json`.
6. Select a materially distinct 3-5-concept test cell in `test-selection.json` and create one approved production-register record per selected concept.
7. Register only approved creative assets. Static, carousel, and video assets use the same approval and provenance contract, but their exact Meta asset IDs must bind to the matching creative payload.
8. Prepare a campaign manifest and run `validate` plus an exact-account read-only check.
9. Require a scoped, unexpired approval before any Meta API write. Set the lifecycle `next_permitted_action` to `create-paused` for paused creation; after a new review, set it to `activate` and require a separate approval to activate one exact object.
10. Keep collected reports immutable. Reconcile coverage in a separate reviewed record before writing a recommendation; never automate a budget or status change from a report.

## Non-negotiable rules

- Never invent proof, testimonials, results, pricing, urgency, capabilities, or policy approval.
- Never put a token or secret in Markdown, JSON, a command argument, or Git.
- Never reuse one account's asset IDs, reports, or approvals in another account.
- Never interpret clicks, leads, or platform events as revenue without a verified downstream reconciliation.
- Never blindly retry a write after timeout or an ambiguous response.
- Do not publish external changes just because a local manifest says approved.

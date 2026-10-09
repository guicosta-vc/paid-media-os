---
name: marketing-os
description: Run a safe, artifact-backed Meta marketing workflow.
version: 0.1.0
author: Gui Costa, Venture Compass
license: License pending owner selection
platforms: [linux, macos, windows]
metadata:
  tags: [marketing, meta, paid-media, operations]
---

# Paid Media OS

Use this skill to initialize or operate the generic Marketing OS. It moves from strategy to creative selection, approved assets, scoped Meta operations, reporting, and explicit decisions. It does not authorize a real campaign change by itself.

## When to use

- A team needs a durable workflow for Meta campaign planning and reporting.
- An agent must connect marketing strategy, creative testing, assets, and decisions.
- A user wants to create paused Meta objects only after review.

Do not use this skill to bypass budget, activation, claim, customer, or platform-policy approval.

## Procedure

1. Read `AGENT_GUIDE.md`, `SECURITY.md`, and `templates/strategy-lock.md`.
   Completion: known facts, assumptions, and prohibited claims are separate.
2. Initialize a private workspace with `python3 scripts/mos.py init --workspace <private-path>`.
   Completion: configuration and blank operating artifacts exist, with no secret in them.
3. Use `creative-bank/SKILL.md` before asset production.
   Completion: exactly 50 concepts exist and a 3-5-item cell is selected.
4. Register only approved static or video assets in `creative-catalog.json`.
   Completion: every selected asset has a checksum, rights status, approval state, and verified Meta asset ID.
5. Prepare and validate the campaign manifest with `python3 scripts/mos.py validate --workspace <private-path>`.
   Completion: the manifest, assets, account ID, and target status reconcile.
6. Use `meta-operations/SKILL.md` for reads or writes.
   Completion: a read receipt or a write receipt plus exact read-back exists.
7. Use `reporting-decisions/SKILL.md` after a complete reporting window.
   Completion: the recommendation is bounded by evidence and names any new approval needed.

## Safety rules

- Campaign creation begins paused and needs an unexpired `CREATE_PAUSED` approval.
- Activation needs a different `ACTIVATE` approval.
- No budget increase is automated or implemented by this repository.
- On an uncertain external write, stop and read back exact objects before any retry.

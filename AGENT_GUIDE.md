# Agent Guide

Paid Media OS is a generic, artifact-backed workflow. Do not treat it as permission to spend money, publish ads, change tracking, or infer customer facts.

## Required operating order

1. Read `README.md`, `SECURITY.md`, and the relevant skill under `skills/`.
2. Create a private local workspace with `python3 scripts/mos.py init`.
3. Complete strategy and claim boundaries before producing creative concepts.
4. Build exactly 50 concepts only after the Strategy Lock is approved.
5. Select a materially distinct 3-5 concept test cell; retain the other concepts as a backlog, not as a launch list.
6. Register only approved creative assets. Static and video assets use the same approval and provenance contract.
7. Prepare a campaign manifest and run `validate` plus an account read-only check.
8. Require a scoped, unexpired approval before any Meta API write.
9. Create paused objects first. Require a separate approval to activate them.
10. Collect complete reporting windows, label incomplete data, and make a recommendation rather than an automatic budget or status change.

## Non-negotiable rules

- Never invent proof, testimonials, results, pricing, urgency, capabilities, or policy approval.
- Never put a token or secret in Markdown, JSON, a command argument, or Git.
- Never reuse one account's asset IDs, reports, or approvals in another account.
- Never interpret clicks, leads, or platform events as revenue without a verified downstream reconciliation.
- Never blindly retry a write after timeout or an ambiguous response.
- Do not publish external changes just because a local manifest says approved.

## Installation

Read `README.md` for Claude, Hermes, and generic-agent installation paths. Keep this guide and the linked skill references together when copying skills.

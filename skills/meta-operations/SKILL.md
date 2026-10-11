---
name: meta-operations
description: Read Meta safely and create approved paused objects.
version: 0.1.0
author: Gui Costa, Venture Compass
license: Business Source License 1.1 (BUSL-1.1)
platforms: [linux, macos, windows]
metadata:
  tags: [meta, advertising, approvals, security]
---

# Meta Operations

Use this skill for exact-account Meta reads and explicit, approval-gated writes. The CLI uses only `META_ACCESS_TOKEN` from the process environment; it must never receive a token in a file or command argument.

## Read-only procedure

1. Confirm the private workspace has the intended `act_<account-id>`.
2. Set the token privately and run `account-check`.
3. Run `collect` for a named reporting window.
4. Inspect the receipt and raw reporting snapshot locally.

Completion: the report declares account, time window, collection time, and any incompleteness. It does not infer revenue or downstream quality.

## Paused creation procedure

1. Validate the workspace, catalog, and manifest.
2. Verify assets have approved copy, rights, checksum, and verified Meta asset IDs.
3. Create an unexpired `CREATE_PAUSED` approval that names the same account and manifest.
4. Run a dry run, inspect every payload, then make the call only with `--execute` and the exact acknowledgement.
5. Inspect the receipt and exact object read-back.

Completion: the receipt maps every attempted object to a response and read-back. Any uncertain result stops further writes.

## Activation procedure

1. Read back the exact target object and current status.
2. Obtain a separate, unexpired `ACTIVATE` approval for the same account.
3. Use `activate` with the explicit acknowledgement.
4. Inspect the read-back receipt.

Completion: the result distinguishes configured status, effective status, review state, and any platform error. Never activate an object that is disapproved or unverified.

## Never do

- Do not list broad accounts as a substitute for exact-account verification.
- Do not create active objects from the paused creation flow.
- Do not retry an ambiguous POST.
- Do not automatically change a budget, tracking event, audience, or campaign status.

# Implementation guide

This guide is for a company running its own advertising or an agency operating isolated client workspaces. It is an operating framework, not legal, platform-policy, or performance advice.

## 1. Create one private tenant workspace

Copy `templates/tenant-intake.md` and `templates/lifecycle-state.example.json` into a private tenant directory. Record the tenant ID, accountable owner, permitted account scope, credential alias, evidence, blockers, and next permitted action. Never put credentials, client exports, or account identifiers in this repository.

## 2. Complete the Strategy Lock

Use `templates/strategy-lock.md`. Separate verified source facts from assumptions. State the conversion event, measurement semantics, economics, claims allowed, prohibited claims, owner, version, approver, and approval expiry. A changed or superseded lock requires a new review.

## 3. Initialize the operating workspace

Run `python3 scripts/mos.py init --workspace <private-path>`. The first validation failure is expected: replace all placeholders, add the tenant and account scope, complete the asset catalog, and finish the private artifacts before validating.

## 4. Build the 50-SKU creative bank

Use `templates/creative-bank.md` and `skills/creative-bank/SKILL.md`. Complete all ten categories and five stable SKUs in each category. Every SKU needs a claim status, hypothesis, copy, CTA, visual job, evidence requirement, and eligibility outcome.

## 5. Select the initial test cell

Use `templates/test-selection.example.json`. Choose exactly three to five eligible SKUs that test materially different hypotheses. Keep rejected near-misses and the reason they were not selected.

## 6. Hand off static, carousel, or video production

Create one private `templates/production-handoff.md` for every selected SKU. Specify exact approved copy, visual direction, placements, aspect ratios or duration, rights, proof, accessibility, and reviewers. Register only QA-approved assets with checksum, provenance, dimensions or duration, and the verified platform asset ID.

## 7. Build a paused-only manifest

Complete `campaign-manifest.json` with the same tenant and account scope as the workspace. The CLI accepts only an exact endpoint for each object type and rejects active status. Review the manifest, compute its canonical SHA-256 digest, and record that digest in the private `CREATE_PAUSED` approval.

## 8. Validate, dry-run, then create paused objects

Run validation and inspect the dry run before any external write. A human operator must provide the environment-only token, unexpired approval, and explicit acknowledgement. Reconcile exact API read-backs; never retry an uncertain POST.

## 9. Activate only a bound, approved object

Activation requires a separate unexpired approval naming the exact object ID and object kind. The runner reads the object, confirms its account scope, and records a receipt. Budget changes, audience changes, tracking changes, and unscoped activation are outside this starter kit.

## 10. Report and decide

Collect a named date range in the account timezone. Preserve a private immutable snapshot and distinguish delivery metrics from downstream evidence. Use `keep`, `kill`, `remix`, `defer`, `insufficient-data`, or `blocked` only with the linked hypothesis, stated threshold, rationale, and next approval.

## Agency isolation rule

Do not mix tenant IDs, accounts, assets, reports, approvals, or credential aliases. One tenant’s artifacts and runtime credentials must never be selected for another tenant. Keep every workspace private and export only sanitized, approved material.

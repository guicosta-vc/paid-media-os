# Implementation guide

This guide is for a company running its own advertising or an agency operating isolated client workspaces. It is an operating framework, not legal, platform-policy, or performance advice.

## 1. Create one private tenant workspace

Run `python3 scripts/mos.py init --workspace <private-path>`. Keep this workspace outside Git and outside any shared agent knowledge base. Complete `tenant-intake.md` and `lifecycle-state.json`. The lifecycle record is authoritative for operating state: it must name the tenant, exact account, accountable owner, tracking evidence, blockers, and next permitted action.

## 2. Complete the Strategy Lock

Use `strategy-lock.md`. Separate verified source facts from assumptions. State the conversion event, measurement semantics, economics, claims allowed, prohibited claims, owner, version, approver, and approval expiry. Record the completed, unexpired approval in `strategy-approval.json` with the same tenant and Strategy Lock version as `workspace.json`.

## 3. Build the 50-concept creative bank

Use `creative-bank.md` and `skills/creative-bank/SKILL.md`. Complete all ten categories and five stable SKUs in each category. Every SKU needs a claim status, hypothesis, copy, CTA, visual job, evidence requirement, and eligibility outcome. Record exactly 50 unique concepts in `creative-bank-register.json`.

## 4. Select the initial test cell

Use `test-selection.json`. Choose exactly three to five eligible SKUs that test materially different hypotheses. Keep rejected near-misses and the reason they were not selected. Every selected concept must have one matching approved entry in `production-register.json`.

## 5. Hand off static, carousel, or video production

Create one private `production-handoff.md` for every selected SKU. Specify exact approved copy, visual direction, placements, aspect ratios or duration, rights, proof, accessibility, and reviewers. Register only QA-approved assets with checksum, provenance, dimensions or duration, and verified platform asset IDs.

For each asset, list `meta_asset_ids` in `creative-catalog.json`. Bind a static image or carousel image exactly through `image_hash`; bind video exactly through `video_id`. The manifest's creative object names the catalog `creative_asset_id`. The validator rejects a creative payload that uses an unregistered or mismatched Meta asset ID.

## 6. Build a paused-only manifest

Complete `campaign-manifest.json` with the same tenant and account scope as the workspace. The CLI accepts only exact endpoints for each object type and rejects active status. Campaigns, ad sets, and ads must request `PAUSED`; ad creatives are bound to paused ads and do not carry a delivery status themselves. Review the manifest, compute its canonical SHA-256 digest, and record that digest in the private `CREATE_PAUSED` approval.

## 7. Validate, dry-run, then create paused objects

Run validation and inspect the dry run before any external write. A human operator must provide the environment-only token, unexpired approval, and explicit acknowledgement. The runner persists a receipt before each POST, captures returned object IDs immediately, validates the exact account scope and paused status on read-back, and stops on the first uncertain result. Never retry an uncertain POST.

## 8. Activate only a bound, approved object

Activation requires a separate unexpired approval naming the exact object ID and object kind, plus a lifecycle record whose `next_permitted_action` is exactly `activate`. The runner reads the object, confirms its account scope, persists its receipt before POST, and verifies active status afterward. Budget changes, audience changes, tracking changes, and unscoped activation are outside this starter kit.

## 9. Report and decide without rewriting evidence

Collect a named date range in the account timezone. The raw report is immutable and starts with unknown coverage. Reconcile paging, time window, and downstream evidence in a separate `report-reconciliation.json` that names the source report, its SHA-256, the review method, evidence references, reviewer, and scope. Run `reconcile`, then use the same bound reconciliation in `decide`.

Use `keep`, `kill`, `remix`, `defer`, `insufficient-data`, or `blocked` only with the linked hypothesis, stated threshold, rationale, and next approval. A recommendation is never an automatic budget or status action.

## Agency isolation rule

Do not mix tenant IDs, accounts, assets, reports, approvals, or credential aliases. One tenant's artifacts and runtime credentials must never be selected for another tenant. Keep every workspace private and export only sanitized, approved material.

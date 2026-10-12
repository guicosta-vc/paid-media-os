# Security Policy

## Never commit secrets

Do not commit access tokens, passwords, cookies, account IDs tied to a customer, private URLs, exported reports with personal data, or raw API responses.

Use environment variables for runtime credentials. The supplied `.env.example` contains no credential values. Keep real `.env` files outside version control.

## Scope before every Meta request

Before a read, confirm the target account ID is the intended account. Before a write, confirm the campaign manifest, asset IDs, approval record, expiry, budget, and target status all refer to that exact account.

## Write safety

This repository never writes to Meta by default. A write command needs all of:

1. A matching, unexpired local approval record.
2. An explicit `--execute` flag.
3. `META_ACCESS_TOKEN` in the process environment.
4. A runtime acknowledgement string.

Paused creation and activation are separate actions. Do not set a campaign, ad set, creative, or ad to active through a paused-creation command. On an uncertain write, stop and reconcile exact objects before attempting another write.

## Reporting data

Reports may contain account or campaign information. Keep workspaces private and redact data before sharing examples, issues, or pull requests.

## Reporting a vulnerability

Do not file secrets or reproducible exploit details in a public issue. Report a vulnerability privately to `guicosta@vemturecompass.agency` with the repository name, affected version or commit, impact, and minimal reproduction steps. Use the subject prefix `Paid Media OS security report`.

Do not send tokens, customer data, or raw production responses. You should receive acknowledgement within five business days; if no acknowledgement arrives, send one follow-up to the same address.

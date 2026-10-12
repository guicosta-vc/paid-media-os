# Contributing

## External changes

Paid Media OS does not currently accept external pull requests, patches, documentation submissions, or other contributions for merge. See [CLA.md](CLA.md) for the deterministic contribution-rights policy.

## Feedback and issue reports

You may open a non-sensitive issue that describes a reproducible bug, a safety gap, or a documentation improvement. Do not include credentials, raw exports, client names, customer data, account IDs, private URLs, screenshots with account details, personal data, or proprietary third-party material.

For security-sensitive findings, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

## Maintainer quality standard

Changes made by rights holders or authorized contractors must be original, generic, English-only, and safe by default. They must:

1. Keep external writes disabled by default and require a matching, unexpired approval plus an explicit runtime action.
2. Add or update offline tests for behavior changes.
3. Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
python3 scripts/check_release.py --release
```

Do not claim live Meta behavior from a mocked test. State any Meta API assumption and preserve the relevant approval and safety boundary.

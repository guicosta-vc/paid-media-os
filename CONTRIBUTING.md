# Contributing

Paid Media OS accepts original, generic, English-only improvements that make the operating system safer, clearer, or more useful.

## Before opening a pull request

1. Do not include credentials, raw exports, client names, customer data, account IDs, private URLs, screenshots, or proprietary third-party material.
2. Do not copy prompts, templates, code, or documentation from paid courses, vendors, employers, or customer workspaces.
3. Keep external writes disabled by default and require a matching, unexpired approval plus an explicit runtime action.
4. Add or update offline tests for behavior changes.
5. Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
```

## Pull request standard

Explain the problem, state the approval/safety boundary, list tests run, and call out any Meta API assumptions. Do not claim live Meta behavior from a mocked test.

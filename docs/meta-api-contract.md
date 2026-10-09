# Meta Graph API contract

The CLI intentionally keeps the API layer small and generic.

## Supported reads

- `GET /act_<account-id>` for exact-account identity fields.
- `GET /act_<account-id>/insights` for a dated delivery snapshot.
- `GET /<object-id>` after a controlled write or activation.

## Supported writes

- `POST /act_<account-id>/campaigns`
- `POST /act_<account-id>/adsets`
- `POST /act_<account-id>/adcreatives`
- `POST /act_<account-id>/ads`
- `POST /<object-id>` with `status=ACTIVE` only through the separate activation flow.

A manifest declares raw object payloads because the exact Meta field requirements vary by objective, destination, account configuration, and API version. The runner still rejects an endpoint outside the configured account, an active status in paused creation, missing approval, expired approval, or unresolved dependencies.

## Asset contract

Static assets need a verified Meta image hash. Video assets need a verified Meta video ID. The catalog stores that identifier as `meta_asset_id`. Upload is intentionally outside this initial runner because Meta upload workflows differ by media type, file size, account permissions, and current API requirements. Do not fabricate a media ID.

## Production validation

Before any live write, consult Meta's current official API documentation for your chosen API version, objective, placements, special-ad-category obligations, creative schema, and review policy. A passing local test or dry run does not prove live platform acceptance.

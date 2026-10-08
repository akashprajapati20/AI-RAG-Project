# Tally Cloud REST API Reference (v2)

_API version 2. Last updated: 18 August 2026 (release 4.3.0)._

The Tally Cloud API gives programmatic access to sites, tags, readings, alert rules and forecasts. All requests and responses use JSON.

## Base URLs

Use the base URL for the data region your organisation was created in:

| Region | Base URL |
|---|---|
| EU (Frankfurt) | `https://eu.api.tally.example/v2` |
| US (Virginia) | `https://us.api.tally.example/v2` |
| APAC (Singapore) | `https://ap.api.tally.example/v2` |

Requests sent to the wrong region return `404 not_found` for every resource.

## Authentication

Organisation admins create API keys in **Settings → API Keys**. Send the key as a bearer token:

```
Authorization: Bearer tly_live_3f9a...
```

- Production keys start with `tly_live_`; sandbox keys start with `tly_test_` and only see demo data.
- Keys expire 365 days after creation. You can rotate a key at any time; the old key keeps working for 24 hours after rotation.
- Starter plan keys are always read-only. On Growth and Enterprise, each key is created with either `read` or `read_write` scope.

## Rate limits

Rate limits apply per organisation, not per key:

| Plan | Limit |
|---|---|
| Starter | 120 requests per minute |
| Growth | 600 requests per minute |
| Enterprise | 3,000 requests per minute |

Every response includes `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers. When you exceed the limit, the API responds with `429 rate_limited` and a `Retry-After` header in seconds.

## Pagination

List endpoints use cursor pagination. Pass `limit` (default 50, maximum 200) and the `next_cursor` value from the previous response as `cursor`. When `next_cursor` is `null`, you have reached the last page.

## Endpoints

### `GET /sites`

Lists the sites in your organisation.

### `GET /sites/{site_id}/tags`

Lists the tags at a site. Optional filter: `status=ok|low_battery|offline`.

### `GET /tags/{tag_id}/readings`

Returns weight readings for one tag.

| Parameter | Description |
|---|---|
| `from`, `to` | ISO 8601 timestamps (required) |
| `resolution` | `raw`, `5m`, `1h` or `1d` (default `1h`) |

With `resolution=raw`, the range between `from` and `to` may be at most 7 days. Aggregated resolutions allow any range within your plan's data history.

### `POST /alert-rules`

Creates an alert rule. Requires a `read_write` key.

```json
{
  "site_id": "site_8Hk2",
  "metric": "stock_level",
  "operator": "lt",
  "threshold": 12.5,
  "channels": ["email", "webhook"]
}
```

`metric` is `stock_level` (kg) or `battery` (percent). `channels` can include `email`, `webhook` and `slack`. A site can have at most 500 alert rules.

### `DELETE /alert-rules/{rule_id}`

Deletes an alert rule. Returns `204 No Content`.

### `GET /forecasts/{tag_id}`

Returns the Predictive Restock forecast for a tag: `days_until_empty`, `expected_empty_at` and a `confidence` between 0 and 1. Requires the Predictive Restock add-on (included on Enterprise); otherwise the API returns `403 plan_restricted`. Forecasts are recomputed every 6 hours.

## Webhooks

Configure webhook endpoints in **Settings → Webhooks**. Events:

- `stock.low` — an alert rule on `stock_level` fired
- `tag.battery_low` — a tag's battery dropped below 15%
- `tag.offline` — a tag has not reported for 30 minutes
- `hub.offline` — a hub has had no uplink for 10 minutes

Each delivery is signed with HMAC-SHA256 using your endpoint's signing secret. The `Tally-Signature` header has the form `t=<unix timestamp>,v1=<hex signature>`, where the signature is computed over `"<timestamp>.<raw request body>"`. Reject deliveries whose timestamp is more than 5 minutes old to prevent replay attacks.

Your endpoint must return a 2xx status within 10 seconds. Failed deliveries are retried up to 8 times over 24 hours with exponential backoff; after that the event is dropped and appears in the webhook log as `failed`.

## Errors

Errors return a JSON body of the form `{"error": {"code": "...", "message": "...", "request_id": "..."}}`. Include the `request_id` when contacting support.

| HTTP status | Code | Meaning |
|---|---|---|
| 400 | `invalid_request` | Missing or malformed parameters |
| 401 | `unauthorized` | Missing, invalid or expired API key |
| 403 | `plan_restricted` | Your plan does not include this feature |
| 403 | `insufficient_scope` | The key is read-only |
| 404 | `not_found` | Resource does not exist (or wrong region) |
| 409 | `conflict` | For example, a duplicate alert rule |
| 429 | `rate_limited` | Rate limit exceeded |
| 500 | `internal_error` | Unexpected server error; safe to retry |

## API v1

API v1 is deprecated since release 4.2.0 and will be switched off on 31 December 2026. Migrate to v2 before then; v1 requests already return a `Deprecation` header.

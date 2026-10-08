# Tally Release Notes

## 4.3.0 — 18 August 2026

**New**
- Bulk recalibration: recalibrate all tags on a shelf row in one step from the dashboard.
- Slack is now generally available as an alert channel (previously beta).
- Hub firmware 5.8: faster switch to LTE fallback (under 20 seconds instead of about 2 minutes).

**Fixed**
- Daily stock reports used UTC instead of the site's time zone for the report cut-off.
- Tags occasionally showed as `offline` for a few minutes after a hub firmware update.

**Known issue**
- Exporting readings to CSV from the dashboard times out for date ranges longer than 90 days. Workaround: use the API endpoint `GET /tags/{tag_id}/readings` with `resolution=1d`, or export in chunks of 90 days.

## 4.2.0 — 7 April 2026

**New**
- **Predictive Restock** add-on: machine-learning forecasts of how many days remain until each shelf is empty, based on the last 90 days of consumption. Available as a paid add-on on Growth and included on Enterprise.
- New API endpoint `GET /forecasts/{tag_id}`.

**Deprecated**
- API v1 is deprecated. It will be switched off on 31 December 2026.

## 4.1.0 — 2 December 2025

**New**
- SAML single sign-on for Enterprise organisations.
- Audit log export to CSV and to S3-compatible storage.
- Tag firmware 2.4.0 with a new radio duty cycle that improves battery life by about 15%.

## 4.0.0 — 23 June 2025

**New**
- Redesigned dashboard with a floor-plan view of shelves.
- Support for the cold-storage tag TT-200C.
- Webhooks v2 with HMAC-SHA256 signatures.

**Removed**
- Unsigned (v1) webhooks were removed on 1 October 2025.

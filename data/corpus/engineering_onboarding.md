# Engineering Onboarding Guide

_Owner: Adaeze Okafor, VP Engineering. Last updated: 5 May 2026._

Welcome to Brindlewave Engineering! This guide covers how we build, ship and run Tally. Your onboarding buddy will walk you through it in your first week — ask them anything, or post in the `#eng-help` Slack channel.

## Tech stack

- **Backend services:** Go (ingestion, alerts, billing) and Python (forecasting / Predictive Restock).
- **Frontend:** TypeScript and React for the dashboard.
- **Data:** PostgreSQL with TimescaleDB for telemetry; Kafka as the event backbone between services.
- **Infrastructure:** Kubernetes on AWS, one cluster per data region (EU, US, APAC), managed with Terraform. Deployments go through Argo CD.
- **Observability:** Prometheus and Grafana for metrics, Loki for logs, PagerDuty for paging.

## Main repositories

| Repository | Contents |
|---|---|
| `tally-ingest` | Receives readings from hubs and writes them to TimescaleDB |
| `alert-service` | Evaluates alert rules and sends notifications |
| `tally-forecast` | Predictive Restock models and the forecast API |
| `tally-web` | Dashboard frontend |
| `billing-service` | Plans, invoices, SLA credits |
| `infra` | Terraform, Kubernetes manifests, Argo CD config |

## Your first week

1. Get laptop, SSO and a hardware security key from IT on day one.
2. Run `make dev` in `tally-ingest` to start the local stack (Docker Compose with seeded demo data).
3. Ship a small change to production by Friday — your buddy will pick a starter ticket.
4. Shadow an on-call shift in your second or third week.

## Code review

- Every pull request needs at least 1 approving review.
- Changes to `billing-service` and to anything under `infra/prod/` need 2 approvals, one of them from a code owner.
- Keep pull requests under about 400 changed lines where possible.

## Deploying

Merges to `main` deploy automatically to staging, then to production after automated checks pass. There is a **deploy freeze on Fridays after 15:00 CET** and during company closures such as recharge week. During a freeze, only hotfixes approved by the current incident commander may be deployed. Since INC-2026-031, any change to Kafka consumer configuration must pass a load test in staging first.

## On-call

- Rotation is weekly; handover is on **Monday at 10:00 CET**.
- P1 pages must be acknowledged within 15 minutes, P2 pages within 30 minutes.
- On-call engineers receive an allowance of €350 per on-call week.
- New engineers join the rotation after 3 months.

### Severity levels

| Severity | Definition |
|---|---|
| P1 | Customer-facing outage or data loss, or more than 5% of sites affected |
| P2 | Significant degradation for some customers, with a workaround available |
| P3 | Minor issue with no significant customer impact |

A blameless postmortem is required for every P1 and P2 incident and must be published within 5 business days of resolution.

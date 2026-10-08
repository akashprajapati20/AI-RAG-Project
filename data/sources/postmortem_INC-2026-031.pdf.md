# Postmortem INC-2026-031: Delayed Stock Alerts in the EU Region

Severity: P1. Date of incident: 17 March 2026. Status: closed. Incident commander: Lars Mikkelsen (Site Reliability Engineering). This postmortem is blameless.

## 1. Summary

For 3 hours and 47 minutes (08:52 to 12:39 CET), stock alerts in the EU region were delayed by up to 3 hours, and the dashboard showed stale stock levels. 1,214 EU sites were affected, about 41% of all EU sites. No data was lost: tag readings were buffered and processed once the system recovered.

## 2. Root cause

On the evening of 16 March, a configuration change reduced the Kafka consumer setting max.poll.interval.ms for the alert-service consumer group from 300 seconds to 30 seconds. The change was intended to detect stuck consumers faster.

During the morning load peak, the forecast-enrichment step inside alert processing took longer than 30 seconds for large batches. Kafka treated those consumers as dead and removed them from the group, which triggered a partition rebalance. Each rebalance paused consumption for all consumers, the backlog grew, batches became larger and slower, and the cycle repeated (a "rebalance storm").

## 3. Detection

The incident was detected at 09:20 CET from customer support tickets, 28 minutes after it started. There was no alert on consumer lag for the alert-service consumer group, so monitoring did not catch it.

## 4. Timeline (CET)

| Time | Event |
|---|---|
| 16 March, 19:05 | Configuration change deployed to production |
| 17 March, 08:52 | Consumer lag starts growing; first rebalance |
| 09:20 | Support escalates customer tickets; incident declared as P1 |
| 09:41 | Status page updated manually |
| 10:30 | Rebalance storm identified as the cause |
| 11:58 | Configuration change reverted |
| 12:39 | Backlog fully processed; incident resolved |

## 5. Impact on customers

The incident counted as downtime for the affected sites. Customers whose monthly uptime for March fell below their plan's SLA were eligible for service credits, and 212 credits were issued, mostly to Growth and Enterprise customers. Around 60 customer support tickets were opened during the incident.

## 6. What went well

- Hub offline buffering meant no readings were lost.
- Rolling back the configuration took less than 5 minutes once the cause was known.

## 7. Action items

| Action | Owner | Due date | Status |
|---|---|---|---|
| Add consumer-lag alerts for every consumer group (page when lag exceeds 5 minutes) | Lars Mikkelsen | 28 March 2026 | Done |
| Require a staging load test for any Kafka consumer configuration change | Adaeze Okafor | 15 April 2026 | Done |
| Move forecast enrichment out of the synchronous alert path | Mei Tanaka (Forecasting team) | 30 May 2026 | In progress |
| Update the status page automatically from the incident tool | Sofia Brandt (Support Operations) | 30 April 2026 | Done |

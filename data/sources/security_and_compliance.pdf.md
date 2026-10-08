# Tally Security and Compliance Overview

Prepared by the Brindlewave Security Team (Jonas Weber, Head of Security). Last reviewed: 20 January 2026.

## 1. Certifications

- **SOC 2 Type II.** The most recent report covers 1 January 2025 to 31 December 2025 and was issued by the independent auditor Halden & Rook LLP. Customers under NDA can request it through their account manager.
- **ISO/IEC 27001:2022.** Brindlewave has been certified since June 2023. The certificate covers Tally Cloud, hub firmware development and customer support operations.

## 2. Encryption

All customer data is encrypted at rest with AES-256. Data in transit is protected with TLS 1.3. TLS 1.2 is still accepted for hubs running firmware older than 5.0; support for TLS 1.2 will be removed on 31 March 2027. Encryption keys are managed in a cloud KMS and rotated every 12 months.

## 3. Data residency

Each customer organisation chooses a data region when it is created:

- EU: Frankfurt (eu-central)
- US: Virginia (us-east)
- APAC: Singapore (ap-southeast)

Customer data never leaves its region, except for anonymised, aggregated product metrics. Moving an existing organisation to a different region is only available on the Enterprise plan.

## 4. Data retention and deletion

- Telemetry (tag readings) is retained according to the plan: 13 months on Starter and 25 months on Growth and Enterprise.
- Audit logs are retained for 400 days on all plans.
- When a customer closes their account, all customer data is permanently deleted within 30 days.
- Backups are retained for 35 days, after which deleted data is also gone from backups.

## 5. Backups and disaster recovery

Databases are backed up every 6 hours to a separate availability zone, and backups are encrypted. The recovery point objective (RPO) is 6 hours and the recovery time objective (RTO) is 4 hours. Disaster-recovery restores are tested every quarter.

## 6. Access control

Enterprise customers can enforce single sign-on with SAML. Two-factor authentication has been mandatory for all customer admin accounts since September 2025. Internally, production access requires hardware security keys, is granted just-in-time for at most 8 hours, and every session is logged.

## 7. Security testing

An independent penetration test is performed every year, most recently in October 2025. Brindlewave runs a public bug bounty programme with payouts of up to $15,000 for critical vulnerabilities. Vulnerabilities can be reported to security@brindlewave.example.

## 8. Incident and breach notification

Customers are notified within 48 hours of a confirmed security breach affecting their data. Where required by GDPR, the relevant supervisory authority is notified within 72 hours. Service incidents that are not security-related are published on the status page.

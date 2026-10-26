# Dunora | Executive Brief

**One-line pitch:** Dunora helps service businesses collect receivables faster through accurate balances, explainable follow-up priorities, and human-approved customer outreach.

## Problem / market friction

Service agencies, wholesalers and project-based small businesses frequently manage unpaid invoices in CSVs, email threads and spreadsheets. It is easy to lose track of partial settlements or send the wrong customer a follow-up. Mistakes cost time, strain client relationships and undermine cash-flow planning. The first user to serve is **a 3–30-person professional services company** with 25–500 active invoices, no dedicated collections platform and an operations lead juggling finance work.

## Unique insight

A flashy predictive model is less valuable than trust in the ledger. Dunora makes every action inspectable: what balance is outstanding, why an account was ranked high, whether an invoice is disputed, whether a follow-up was approved, whether a message was truly delivered, and how much the buyer paid. This is **evidence-first automation**, not an unsupervised debt-collection bot.

## Product mechanism

CSV/import → validated invoice ledger → partial-payment records → deterministic risk score (shown factor by factor) → human-reviewable reminder → audit trail → continuously updated collections dashboard.

Three product benefits are measurable, but unproven until real trials:
- Minutes spent preparing a weekly collections queue (before/after).
- Average days sales outstanding, measured monthly on real customer data.
- Incorrect or inappropriate reminders prevented through dispute and payment checks.

## Business model / capture of value

- **Starter:** free, up to 25 invoices. Organic funnel and low-friction evaluation.
- **Growth:** ₹1,499/month for growing teams using CSV ingest and reminder workflows.
- **Scale:** ₹4,999/month intended for team governance and integrations once built.
- Optional future add-ons: transaction-volume tiers, integrations, audit retention and white-label client portals. No outcome-based commission unless approved and appropriate.

**Illustrative unit economics (assumptions, not traction):** If 100 paying customers adopt Growth, gross MRR = ₹149,900 and annualized recurring revenue = ₹1,798,800 before payment fees, taxes, cloud/SMTP/API costs, churn and refunds. Acquisition cost, churn and sales conversion must be validated through pilots.

## Go-to-market

Start with 10–15 interviews with Indian and global agencies, accountants and distributors. Recruit five design partners willing to upload anonymized invoice histories, compare weekly follow-up effort and give permission for aggregated outcome reporting. Publish results only from measured data. Target accountants/bookkeepers for referral partnerships. Do not claim pilots or customers until there are signed agreements.

## Enterprise narrative

No auto-sending, every reminder can be edited, disputes pause outreach, all money calculations use integer minor currency units, approvals produce audit events, and every query is scoped to a tenant. Stripe subscription checkout and optional SMTP delivery have real server-side integrations when configured, otherwise the interface discloses unavailable integrations.

## MVP boundaries

Implemented: registration/login, isolated demo, invoices, CSV import, partial/full payment reconciliation, transparent risk sorting, dispute pauses, human-approved outreach, SMTP simulation/live integration, audits/export, billing UI and optional Stripe Checkout/webhooks, automated API tests and Docker/Render deploy package.

Not yet implemented: PDF invoice extraction, invoice payment portal, native accounting integrations, team invites/RBAC, production-scale rate limiting, fully implemented Scale features, autonomous AI scoring, enterprise compliance certifications, verified revenue and live public deployment.

## Defensibility roadmap

1. Permissioned, verified cash-flow signals across ledger/CRM/email tools.
2. Adaptive collection playbooks with strictly scoped automated actions.
3. Benchmarking with strong privacy-preserving aggregation.
4. Reliable workflow integrations that reduce manual switching costs.

Built for the official Nexus V2 SaaS criteria; high scores depend on executing the live deployment, credible testing and polished video, not this document alone.

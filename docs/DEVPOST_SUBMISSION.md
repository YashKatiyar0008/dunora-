# DEVPOST COPY — Dunora

**Title:** Dunora — Evidence-First Revenue Operations

**Tagline:** Stop chasing. Start collecting. Know exactly who owes what, why they're at risk, and what to do next.

## Inspiration
Small service businesses spend too much time reconciling invoices across spreadsheets and drafting follow-ups. An AI agent that hallucinates who owes what can do real financial harm. We wanted useful automation without surrendering financial accuracy or customer trust.

## What it does
Dunora takes invoice data, computes actual balances from recorded payments, transparently prioritizes at-risk accounts, prepares editable collection follow-ups, pauses outreach for disputes, and logs actions for accountability. A demo workspace is one click away so judges can test the entire lifecycle immediately.

## How we built it
FastAPI, SQLAlchemy, PostgreSQL, Pydantic, original dependency-light HTML/CSS/JavaScript UI, Docker, Render Blueprint, GitHub Actions, optional Stripe subscription API, optional SMTP. No open-ended LLM decisions are trusted for accounting facts.

## Challenges
Designing financial workflows where auditability matters more than flashy generated text. We use integer minor units, reject overpayments and duplicate references, scope records by organization, and keep a human in the loop before sending reminders.

## Accomplishments
An end-to-end demonstrable SaaS MVP with isolated tenants, deterministic risk explanations, reminder approvals, audit log, data import, subscriptions integration points, cloud deployment configuration, and API regression tests. (Do not claim external deployment, customers or processed subscriptions until completed.)

## What comes next
Production-grade throttling and authentication, verified cloud backups, receipt scanning, accountant integrations, payment portals, team RBAC, and measured pilots with service businesses.

## Links — FILL BEFORE SUBMITTING
- Live production demo: [ADD ACTUAL HTTPS LINK]
- Public GitHub repository: [ADD ACTUAL REPOSITORY LINK]
- 2–5 minute product video: [ADD ACTUAL YOUTUBE/VIMEO LINK]
- Demo access: click “Explore with an instant demo” on login

**Origin note:** Code created for this challenge; disclose actual contributors and preserve authentic commit history. All example company data is synthetic.

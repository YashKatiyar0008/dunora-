# Security / Compliance Overview

## Assets and boundary

- Primary assets: customer contact emails, receivable balances, payment references and outreach text.
- Trust boundaries: public browser, authenticated API, SQL storage, SMTP provider, Stripe webhooks.
- Data classification: business-sensitive, with potentially personal contact details; do not place real accounts into public demo workspaces.

## Implemented guardrails

- Scoped queries by org_id and opaque 7-day login sessions with hashed secrets stored server-side.
- Strong random salts and PBKDF2-HMAC-SHA256 password derivation; HttpOnly SameSite=Strict cookies; HTTPS cookie flag is configurable.
- Enforced origin for state-changing requests from browsers; CSP, frame and sniffing headers.
- Unique invoice/payment identifiers; bounded CSV uploads; duplicate rejection; manual payment reference; integers for money.
- Sensitive outbound message review with explicit approval; disputed and fully settled invoices blocked.
- Audit recording for mutations; audit export CSV escapes spreadsheet formulas.
- Signed Stripe webhook events are required; no plan upgrade based on user-controlled success URLs.

## Threat model (selected)

| Threat | Status | Mitigation / next step |
|---|---|---|
| Accessing a different tenant's invoice | Tested | org_id scoped query; non-owned IDs result in 404 |
| CSRF | Basic protection | Strict cookie + Origin validation; require deployment testing behind load balancer |
| Precision mistakes and overpayments | Tested | integer paise; rejecting overpayments and duplicate references |
| Inappropriate debt reminder | Tested | human approval, dispute block, simulated dispatch default |
| Stripe forged webhook | Basic protection | HMAC-SHA256 + timestamp tolerance; add replay event store |
| Brute-force account access | Not production-ready | Add distributed throttling, MFA, password resets and abuse monitoring |
| Multi-region scaling | Not included | External queue, migrations, replicated DB, load tests and observability |
| Data retention and erasure | Not included | Publish policy and implement self-service export/deletion |
| User role segregation | Future | Owner-only permissions, member roles, organization invites |
| Invoice bank fraud | Outside app | Reconciliation is manually recorded; do not treat the UI as bank verification |

## Go-live checklist

- [ ] Paid/managed PostgreSQL with backups, encryption and least privilege
- [ ] Production HTTPS origin and `COOKIE_SECURE=true`
- [ ] CAPTCHA/WAF and durable rate limiting for demo/auth endpoints
- [ ] Alembic migrations and database constraints reviewed
- [ ] Email deliverability + consent/privacy notices and provider setup
- [ ] Webhook replay/idempotency and subscription reconciliation
- [ ] Billing tests with Stripe test mode and business tax invoices
- [ ] Metrics, traces, Sentry or equivalent and alerting
- [ ] Right-to-delete/export workflows and legal/privacy documents
- [ ] Dependency scanning, accessibility audit, load test and pentest

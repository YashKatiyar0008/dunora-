# Dunora Nexus V2 — Premium Dashboard Upgrade

## Delivered

Reference-inspired original dark navy SaaS UI with glowing color-coded KPI cards, compact sidebar navigation, stage-based collections flow, real-time invoice-state donut, six-month invoiced-vs-collected trend, dense invoice ledger, and 390-pixel mobile-responsive layout.

## Where to edit

- `app/static/index.html`: sidebar and top navigation.
- `app/static/v2.css`: new production UI styling and breakpoints.
- `app/static/app.js`: dashboard renderer, SVG chart calculation, click handlers, and pre-existing invoice/payment/reminder workflows.
- `app/main.py`: existing backend (not changed for this UI release).

## Real metrics, not fabricated features

- Total invoiced = sum of invoice face amounts.
- Open receivables = sum of positive unpaid balances.
- Collections logged = sum of payments reconciled in the ledger.
- Collection rate = collections logged / total invoiced (value-weighted).
- Overdue amount = unpaid balance of overdue invoices.
- Four stages: invoices due more than seven days away, due within seven days, overdue, and unapproved reminder drafts.
- Donut: overdue, upcoming, paid, disputed invoice counts.
- Trend lines: amounts from payments and invoice issue dates in the last six calendar months.

Clicking stage cards opens the applicable invoice ledger or Collection Studio. The existing human-approval rule still applies to sending follow-ups. Stripe and SMTP require credentials and are not configured by this UI release.

## Quality checks

Seven backend tests pass. Desktop and 390px-mobile screenshots were reviewed; browser tests confirmed navigation, modal interaction, no JS console errors, and no document-level horizontal overflow. Local UI captures used the running FastAPI backend with a browser request bridge because direct loopback navigation was restricted in the execution browser environment.

This is an original implementation guided by a user-provided visual reference, not a copy of ZenPay branding, data, or code.

# Dunora Nexus V2 — Premium Interface

**A working SaaS MVP built for Galuxium Nexus V2, not a deployed service.**

## 1. Start the app locally

From this directory on **macOS / Linux**:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

On **Windows PowerShell**:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then visit **http://127.0.0.1:8000** and select **Explore with an instant demo**. No Stripe or email credentials are necessary for the demonstrable core workflow. The fictional demo creates a new isolated company with 13 invoices.

If you have Docker, alternatively run `docker compose up --build` to use PostgreSQL instead of the default local SQLite file.

## 2. Test it

```bash
python -m pytest -q
```

Seven automated tests cover tenant isolation, precise partial payments, overpayment and duplicate protections, dispute controls, reminder simulations, origin/auth checks, CSV ingest and demo onboarding.

## 3. Explore a real workflow

Demo login → premium dark command center with live KPI cards, collections journey and charts → Overview → Invoices → open an invoice → record partial payment → Collection studio → generate and edit a follow-up → approve simulated dispatch → Activity log → Plans & billing. Import `app/static/sample.csv` into a fresh real workspace if preferred.

## 4. Deploy Dunora on Render without selecting paid plans

Follow **`DEPLOY_RENDER_FREE.md`**. The included `render.yaml` now explicitly requests **Free web hosting and Free PostgreSQL** in Singapore. The database expires 30 days after creation and has no managed backups. No live Stripe or SMTP features are configured.

Create the public GitHub repository `dunora-nexus-v2`, publish the project files and connect the repository to Render as a Blueprint. Confirm both resources show **Free** before approving. The app will pick up its Render HTTPS URL automatically.

## 5. Submission documents already included

- `README.md`: architecture, dependencies, schema, deployment and honest production caveats.
- `docs/EXECUTIVE_BRIEF.md`: market, users, tech and revenue design.
- `docs/DEVPOST_SUBMISSION.md`: copy-ready Devpost entry (fill live links first).
- `docs/DEMO_VIDEO_SCRIPT.md`: narrated 3-minute keynote plan.
- `docs/01-login.png` ... `docs/11-billing.png`: UI screenshots.
- `docs/SECURITY.md`, `docs/PLAN_TO_DEADLINE.md`: security limits and closing plan.

## What remains genuinely unfinished?

**Public URL, repository publication, real Stripe account/webhook testing, verified email delivery, customer validation and final hosted keynote video.** These require external accounts and are deliberately not represented as done. See README for further production hardening work (MFA, distributed rate limiting, backups, migrations, observability and independent security review). No prize win or live sales are guaranteed.

## Design preview

- `docs/dashboard-v2-desktop.png`: updated desktop dashboard.
- `docs/dashboard-v2-mobile.png`: responsive mobile view.
- `docs/03-invoices.png`, `docs/07-collection-studio.png`, `docs/10-audit.png`, `docs/11-billing.png`: refreshed dark-theme secondary pages.

The included earlier walkthrough video still shows the initial interface. For submission, re-record the live website with this updated visual design.

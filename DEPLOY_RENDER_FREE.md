# Deploy Dunora V2 to Render for $0 (demonstration use only)

## What is prepared
The app runs as a Python 3.12 Docker FastAPI web service with a PostgreSQL database. `render.yaml` requests **plan: free** for BOTH, with Singapore region and HTTPS session cookies. `APP_URL` automatically uses Render's `RENDER_EXTERNAL_URL` when not set. The PostgreSQL database is reachable through Render's internal network only.

## Required GitHub step
1. Create a new **public** repository named `dunora-nexus-v2` at https://github.com/new . Leave README, .gitignore and license unchecked (the supplied folder already includes a README and .gitignore).
2. Upload the **contents** of this `dunora-nexus/` folder, not the zip itself. You can use GitHub's Add file > Upload files. Include `.github/workflows/tests.yml` and `.gitignore` (for hidden files, GitHub website upload behavior may vary; git on Mac is more reliable).
3. A reliable Mac Terminal approach, from this extracted `dunora-nexus/` directory:

```bash
git init
git add .
git commit -m "Add Dunora Nexus V2 app and $0 Render blueprint"
git branch -M main
git remote add origin https://github.com/YashKatiyar0008/dunora-nexus-v2.git
git push -u origin main
```

If GitHub requests authorization, use browser authentication or SSH credentials; never paste access tokens into chat.

## Deploy
Option A: Reply in ChatGPT with the exact GitHub repo URL after uploading. I can then create a free PostgreSQL and free web service using your confirmed Render `My Workspace` and test the resulting URL. The assistant will not create paid resources without your approval.

Option B: In https://dashboard.render.com choose New > Blueprint, connect your GitHub account, select `dunora-nexus-v2` and approve the blueprint once it clearly lists **Web service: Free** and **Postgres: Free**. If any paid plan appears, stop and reject the change.

After deployment, load `https://YOUR-RENDER-URL/api/health` and the base site `/`; click `Explore with an instant demo`, check invoice details and partial payment, and verify that a dispute blocks reminders.

## Important free plan limitations
- Free Render web services may spin down after 15 minutes of inactivity, resulting in a slow first request.
- Free Postgres has 1 GB max storage, expires 30 days after creation and has no backups. It is not for genuine customer financial data.
- Free web instances block outbound SMTP ports 25, 465, 587; notification delivery without a supported alternate provider stays **simulation only**.
- External Stripe keys and price IDs are intentionally NOT configured. No live payments are accepted.
- Instant demo signup is enabled for hackathon judging. Switch `ALLOW_PUBLIC_DEMO=false` if bot traffic or abuse occurs; the app does not implement robust distributed rate limits.
- Do not enter real customer personal/financial information without completing security, consent, monitoring and backups.
- Free monthly allowances may be exhausted. Confirm your workspace usage before deployment; Render can suspend services or bill for overages based on account settings. Set suitable spend limits in your Render billing dashboard.

## Validation

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Expected: 7 tests passing. 

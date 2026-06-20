# LegacyOS Lite on Vercel (Private Demo Deployment)

This repo can be deployed to Vercel as a private repository preview app while keeping
core ownership protections intact.

## What this setup supports

- Single-domain app hosted by Vercel.
- LegacyOS Lite FastAPI API served through a Vercel Python function.
- SQLite data stored in Vercel runtime temp storage (suitable for demo sessions).

Note:
`/api/index.py` points SQLite to `/tmp/legacyoslite.db`, which is ephemeral in serverless hosting.
Use this for demo workflows and not for production persistence.

## 1) Create private GitHub repo

From your existing local history:

```bash
git init
git add .
git commit -m "Prepare LegacyOS Lite for Vercel demo deployment"
git remote add origin git@github.com:YOUR_ORG_OR_USER/legacyos-lite.git
git push -u origin main
```

Set repository visibility to **Private** in GitHub.

## 2) Connect to Vercel

In Vercel:

1. Create/import a new project from your private GitHub repository.
2. Framework detection: `Other`.
3. No custom build step required.
4. Ensure `vercel.json` is used as-is.
5. Set environment variable:
   - `LEGACYOSLITE_ALLOWED_ORIGINS` = `https://<your-vercel-domain>`
   (Optional during first validation; `VERCEL_URL` is detected automatically as fallback.)

If Vercel asks for install/build fields:

- Install Command: `pip install -r requirements.txt`
- Build Command: leave empty
- Output Directory: leave empty

## 3) Recommended deployment guardrails

- Keep the repo private.
- Do not commit `.env` or secrets.
- Share only screenshot/video of the demo UI publicly.
- For stronger persistence, replace `LEGACYOSLITE_DB_PATH` with an external DB during future hardening.

## 4) Quick verification after deploy

- Open the Vercel URL.
- Run through Day 7 flow (interview, graph, timeline, repository note, search).
- Confirm `api` endpoints respond.

## 5) Current Vercel hardening note

The FastAPI backend no longer mounts `public/` through `StaticFiles`.
Vercel serves frontend assets from `public/`, while Python only handles `/api/*`.

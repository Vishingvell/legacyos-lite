# LegacyOS Lite on Vercel

Copyright (c) 2026 Vishalan Karunanithi.
All Rights Reserved.
This repository is published for hackathon review only. No permission is granted to copy, modify, distribute, sublicense, or commercially use this software without written permission.

This repo can be deployed to Vercel as a hackathon review app while keeping the repository ownership notice visible.

## What this setup supports

- Single-domain app hosted by Vercel.
- LegacyOS Lite FastAPI API served through a Vercel Python function.
- Static frontend served from `public/`.
- SQLite data stored in Vercel runtime temp storage (suitable for demo sessions).
- Demo-safe Cloud Engineer and SOC Analyst seed data when the database is empty.

Note:
`/api/index.py` points SQLite to `/tmp/legacyoslite.db`, which is ephemeral in serverless hosting.
Use this for demo workflows and not for production persistence.

## 1) Prepare GitHub repo

From your existing local history:

```bash
git init
git add .
git commit -m "Prepare LegacyOS Lite for Vercel demo deployment"
git remote add origin git@github.com:YOUR_ORG_OR_USER/legacyos-lite.git
git push -u origin main
```

Set repository visibility according to your review needs. For public hackathon review, keep the ownership notice and `LICENSE` file in place.

## 2) Connect to Vercel

In Vercel:

1. Create/import a new project from your GitHub repository.
2. Framework detection: `Other`.
3. Root Directory: `.`.
4. Install Command: `pip install -r requirements.txt`.
5. Build Command: leave empty.
6. Output Directory: leave empty.
7. Ensure `vercel.json` is used as-is.
8. Set environment variable:
   - `LEGACYOSLITE_DB_PATH` = `/tmp/legacyoslite.db`

Optional environment variable:

- `LEGACYOSLITE_ALLOWED_ORIGINS` = `https://<your-vercel-domain>`
  (Usually not required for same-origin app usage. `VERCEL_URL` is detected automatically.)
- `LEGACYOSLITE_SEED_DEMO_DATA` = `false`
  (Only use this if you want the review app to start with no sample profiles or notes.)

## 3) Recommended deployment guardrails

- Keep repository ownership notices in place.
- Do not commit `.env` or secrets.
- Share only demo-safe sample data publicly.
- For stronger persistence during review, replace `LEGACYOSLITE_DB_PATH` with an external database.

## 4) Quick verification after deploy

- Open the Vercel URL.
- Run through Day 7 flow (interview, graph, timeline, repository note, search).
- Confirm `api` endpoints respond.

## 5) Current Vercel hardening note

The FastAPI backend no longer mounts `public/` through `StaticFiles`.
Vercel serves frontend assets from `public/`, while Python only handles `/api/*`.
The `vercel.json` file intentionally avoids a `builds` block so project settings
and automatic Python function handling remain predictable.

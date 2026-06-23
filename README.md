# LegacyOS Lite

Copyright (c) 2026 Vishalan Karunanithi.
All Rights Reserved.
This repository is published for hackathon review only. No permission is granted to copy, modify, distribute, sublicense, or commercially use this software without written permission.

LegacyOS Lite is a knowledge continuity system for capturing the operational knowledge that usually lives in people, meetings, incident reviews, handovers, and scattered runbooks.

The product helps teams answer a simple but expensive question:

```text
If this person or team is unavailable tomorrow, what knowledge do we lose?
```

## Intended Use

LegacyOS Lite is intended for organizations that need to preserve role-specific knowledge before it disappears during staff movement, incident response, audit review, onboarding, or handover.

It is especially useful for roles where hidden context creates operational risk:

- Cloud Engineer
- SOC Analyst
- System Administrator
- Security Engineer
- Software Developer
- Dietician
- Manager

The system is not a chat-only note taker. It builds a structured knowledge profile from interviews and repository notes, then lets users search against that captured evidence.

## Product Workflow

### 1. Capture Role Knowledge

A user selects a role and completes an AI-guided interview. The interview asks about owned systems, critical workflows, incidents, documentation, dependencies, and handover risks.

The system turns the interview into:

- a role summary
- a knowledge profile
- extracted knowledge entities
- relationships between people, systems, processes, sources, and risks
- a continuity risk score
- a timeline of knowledge capture and follow-up events

### 2. Add Repository Evidence

Users can add meeting notes, audit notes, incident reviews, handover summaries, or runbook excerpts in the Knowledge Repository.

Repository notes can be attached to a specific interview or role. This matters because a Cloud Engineer note about CloudFront should not become evidence for an unrelated SOC Analyst question, and a SOC false-positive investigation should not pollute cloud deployment answers.

### 3. Inspect the Knowledge Map

The dashboard shows captured profiles and lets users open a specific profile. Each profile has its own summary, top knowledge nodes, graph, timeline, repository notes, and risk indicators.

The graph view shows how the role connects to systems, processes, risks, knowledge sources, and teams. It is designed as a compact Neo4j-style visualization for demonstration and inspection.

### 4. Ask Evidence-Grounded Questions

AI Knowledge Search answers questions using the best matching profile and repository notes.

Example questions:

- Why did customers see outdated dashboard assets after deployment?
- Why was the SOC incident confirmed as a false positive?
- What fixed the DNS rollback outage for VPN access?
- Who depends on the Cloud Engineer during release incidents?
- What should the next SOC Analyst document before handover?

Search results show the profile used and the evidence sources that supported the answer. Repository evidence can be expanded and inspected directly from the result.

## Search Scoping

LegacyOS Lite deliberately scopes search by role and evidence relevance.

If the current dashboard profile is SOC Analyst but the question asks about CloudFront deployment behavior, search should route to the Cloud Engineer profile and use Cloud Engineer repository notes. If the question asks about SIEM false positives, it should route to SOC Analyst evidence instead.

This prevents one role's notes from overwhelming or contaminating another role's answers.

## Data Handling

LegacyOS Lite stores captured data in SQLite by default.

Local usage:

- Data is stored on the local machine in the configured SQLite database.
- Data remains available between local runs as long as the database file is kept.
- Repository notes can be removed from the UI when sensitive or irrelevant information is captured.

Vercel usage:

- The demo deployment uses SQLite in serverless temporary storage.
- That storage is suitable for review sessions, but it is not durable long-term persistence.
- Fresh empty deployments seed demo-safe Cloud Engineer and SOC Analyst data so reviewers can test search immediately.

Demo seeding can be disabled with:

```bash
LEGACYOSLITE_SEED_DEMO_DATA=false
```

## Local Run

From this folder:

```bash
PYTHONPATH=backend ../.venv/bin/uvicorn legacyos_lite.main:app --reload --port 8010
```

Open:

```text
http://localhost:8010
```

Optional local model configuration:

```bash
LEGACYOSLITE_USE_OLLAMA=true
LEGACYOSLITE_OLLAMA_BASE_URL=http://localhost:11434
LEGACYOSLITE_OLLAMA_MODEL=llama3.2
```

Without Ollama, the app uses deterministic local processing for the hackathon review build.

## Verification

Run the end-to-end product smoke check:

```bash
./tools/demo.sh
```

Run the multi-profile search scoping check:

```bash
PYTHONPATH=backend ../.venv/bin/python tools/search_scope_smoke.py
```

The search scoping check creates Cloud Engineer, SOC Analyst, and System Administrator profiles with separate repository notes, then verifies that cross-role questions retrieve the correct profile and do not leak unrelated evidence.

## Main Components

- `backend/legacyos_lite/main.py` - FastAPI routes and request handling
- `backend/legacyos_lite/ai.py` - deterministic interview processing, extraction, risk scoring, and search answering
- `backend/legacyos_lite/db.py` - SQLite persistence
- `public/` - static dashboard, graph, timeline, repository, and search UI
- `tools/` - local demo and smoke verification scripts
- `docs/` - architecture, deployment, demo script, and sanitized interaction logs

## Deployment

The app can be deployed to Vercel for review. See `docs/VercelDeployment.md`.

The Vercel build is intended for hackathon review and demonstration. For durable organizational usage, configure persistent storage instead of serverless temporary SQLite.

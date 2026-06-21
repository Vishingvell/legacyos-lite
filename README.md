# LegacyOS Lite

Copyright (c) 2026 Vishalan Karunanithi.
All Rights Reserved.
This repository is published for hackathon review only. No permission is granted to copy, modify, distribute, sublicense, or commercially use this software without written permission.

LegacyOS Lite is a hackathon demo that captures role knowledge, generates AI-style summaries, builds a knowledge graph, scores continuity risk, and supports question answering.

This app is intentionally optimized for demo impact and clear product evaluation.

## Current Sprint

Day 7 focus:

- Test and demo readiness for hackathon handoff
- End-to-end smoke checks against all core API paths
- Final demo scope lock for one-week sprint output

### Day 7: Demo Checklist

Run the demo script (recommended before every rehearsal):

```bash
./tools/demo.sh
```

You should see:

- health endpoint success
- at least one configured role loaded
- one interview generated end-to-end
- graph and timeline endpoints responding
- repository note write/read
- search answer generation

Demo script details and presenter flow are in `docs/DemoScript.md`.

Sanitized build interaction logs for hackathon review are in `docs/interaction-logs/`.

## Local Run

From this folder:

```bash
PYTHONPATH=backend ../.venv/bin/uvicorn legacyos_lite.main:app --reload --port 8010
```

Then open in your local browser:

```text
http://localhost:8010
```

Fresh databases automatically seed demo-safe Cloud Engineer and SOC Analyst
profiles with matching repository notes. Disable this with:

```bash
LEGACYOSLITE_SEED_DEMO_DATA=false
```

Deployment options:

- Fast local demo:

  ```bash
  PYTHONPATH=backend ../.venv/bin/uvicorn legacyos_lite.main:app --reload --port 8010
  ```

- Vercel preview (GitHub repo + Vercel):

  1. Import `https://github.com/Vishingvell/legacyos-lite` into a new Vercel project.
  2. Deploy from the latest `main` commit.
  3. Use `docs/VercelDeployment.md` for setup steps.

The Vercel setup is suitable for hackathon demo exposure, but data persistence is
SQLite-backed and ephemeral in serverless runtime by default. Empty Vercel
runtimes seed demo-safe sample data so reviewers can immediately test search,
timeline, graph, and repository evidence.

## Stack

- Backend: FastAPI
- Database: SQLite
- Frontend: Static HTML/CSS/JS
- AI: Local deterministic processing for the hackathon demo, with optional Ollama adapter
- Graph: Browser SVG visualization with Neo4j-shaped nodes and relationships

Enable local model answers by setting:

```bash
LEGACYOSLITE_USE_OLLAMA=true
LEGACYOSLITE_OLLAMA_BASE_URL=http://localhost:11434
LEGACYOSLITE_OLLAMA_MODEL=llama3.2
```

## Demo Journey

1. Select a role.
2. Complete the AI interview.
3. Generate summary, timeline, and knowledge profile.
4. View the knowledge graph.
5. Review risk score.
6. Ask questions through AI Knowledge Search.

## Meeting Notes Ingestion

Operational notes (meeting notes, audits, handoffs, runbooks) are collected in the Knowledge Repository screen and posted via:

- `GET /api/repository/notes` (optional `interview_id`, `limit`)
- `POST /api/repository/notes`

The frontend also supports optional text file upload (`.txt`, `.md`, `.log`, `.csv`, `.json`) in the same form.

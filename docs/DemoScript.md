# LegacyOS Lite Demo Script

## 1) Run the script

From `LEGACYOSLITE`:

```bash
chmod +x tools/demo.sh
./tools/demo.sh
```

This command:

1. Starts the demo server on `127.0.0.1:8010` (default).
2. Optionally runs the Day 7 smoke verification.
3. Leaves the app running for a live demo until you end the script.

## 2) Live demo flow (60–90 seconds)

### Step A: Interview

1. On Dashboard, open **Interview**.
2. Pick one role and complete all prompts with realistic answers (minimum 80 chars each).
3. Click **Generate Profile**.

### Step B: AI output

1. Return to **Dashboard**.
2. Show:
   - generated summary,
   - risk score,
   - top knowledge entities,
   - continuity actions.

### Step C: Knowledge Timeline

1. Open **Timeline**.
2. Point out role progression, critical handoff windows, and risk-sensitive moments.

### Step D: Knowledge Graph

1. Open **Knowledge Graph**.
2. Show generated nodes and relationship links.
3. Click **Export to Neo4j** to show generated Cypher.

### Step E: Repository ingestion

1. Open **Knowledge Repository**.
2. Add a short operational note (meeting notes / audit summary / handoff line).
3. Save and refresh the note list.

### Step F: AI search

1. Open **Search**.
2. Ask one question, e.g.:
   - “What are the highest continuity risks for this role?”
3. Show the response references the graph + repository context.

## 3) Verification command (optional)

Run this at any time:

```bash
PYTHONPATH=backend LEGACYOSLITE_SMOKE_PORT=8011 ../.venv/bin/python tools/day7_smoke.py
```

Expected result: `Smoke checks: PASS`.

## 4) Demo script options

```bash
./tools/demo.sh --help
./tools/demo.sh --no-smoke
./tools/demo.sh --no-open-browser
./tools/demo.sh --no-keep-alive
```

# LegacyOS Lite Architecture

Copyright (c) 2026 Vishalan Karunanithi.
All Rights Reserved.
This repository is published for hackathon review only. No permission is granted to copy, modify, distribute, sublicense, or commercially use this software without written permission.

## Goal

Deliver a working hackathon demo that proves the core product story:

An organization can interview a role holder, extract critical knowledge, visualize dependencies, score continuity risk, and answer questions from captured institutional memory.

## Runtime Shape

```text
Browser UI
  |
  | HTTP/JSON
  v
FastAPI backend
  |
  | sqlite3
  v
SQLite database
```

## Modules

- Interview Engine: role questions and answer capture.
- AI Processor: local summarization, entity extraction, timeline generation, risk scoring, and search responses.
- Knowledge Repository: persisted interviews and generated outputs.
- Timeline: generated events from interview content.
- Graph: entities and relationships exposed as nodes and links for visualization.
- Search: question answering against the generated profile and interview content.

## Database Tables

- `interviews`: one processed interview and generated profile per role session.
- `entities`: extracted people, systems, processes, risks, and controls.
- `relationships`: graph edges between entities.
- `timeline_events`: generated sequence of knowledge events and operational moments.
- `search_queries`: saved demo search questions and generated answers.

## AI Approach

LegacyOS Lite uses deterministic local AI-style processing so the demo can run without network access or a model server.
An optional Ollama adapter is available, but the demo remains usable without external AI services.

## Graph Approach

The demo renders a Neo4j-style graph in the browser from persisted nodes and relationships.
Neo4j export is available as downloadable Cypher while SQLite remains the default demo store.

# Prompt 003 - System Architecture

Copyright (c) 2026 Vishalan Karunanithi.
All Rights Reserved.
This repository is published for hackathon review only. No permission is granted to copy, modify, distribute, sublicense, or commercially use this software without written permission.

## Human Input

The human asked for a working hackathon product with frontend, backend, database, graph, and AI components.

## Architecture Decisions

The selected MVP architecture was:

- FastAPI backend
- SQLite persistence
- Static HTML, CSS, and JavaScript frontend
- Browser-rendered SVG graph
- Deterministic local AI-style processing with optional local model adapter
- Vercel-compatible serverless entrypoint for demo hosting

## AI Assistance

The AI implemented the project structure, API routes, database schema, frontend pages, role interview processing, and deployment configuration.

## Human Review

The human validated that local persistence is important for reliable testing and that Vercel should be treated as a temporary hosted demo unless persistent storage is added.

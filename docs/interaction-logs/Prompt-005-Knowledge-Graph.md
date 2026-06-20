# Prompt 005 - Knowledge Graph

Copyright (c) 2026 Vishalan Karunanithi.
All Rights Reserved.
This repository is published for hackathon review only. No permission is granted to copy, modify, distribute, sublicense, or commercially use this software without written permission.

## Human Input

The human wanted a graph view that could explain role knowledge, systems, people, processes, knowledge sources, and risks.

## Implementation Decisions

The graph MVP renders extracted entities as grouped nodes and relationships as confidence-weighted links.

The graph supports:

- Role-centered visualization
- Group colors for entity types
- Relationship labels and evidence
- Neo4j-style Cypher export

## AI Assistance

The AI implemented the graph payload, SVG layout, labels, export route, and graph page.

## Human Review

The human reviewed screenshots and identified when graph information became too packed. The AI then adjusted graph layout and improved profile switching so each role graph can be viewed separately.

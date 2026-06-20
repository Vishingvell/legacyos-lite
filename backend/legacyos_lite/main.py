# Copyright (c) 2026 Vishalan Karunanithi.
# All Rights Reserved.
# This repository is published for hackathon review only. No permission is granted to copy,
# modify, distribute, sublicense, or commercially use this software without written permission.

from __future__ import annotations

from pathlib import Path
import os
from typing import Any

from fastapi import Request
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from legacyos_lite.ai import ROLE_QUESTIONS, answer_question, generate_interview_package
from legacyos_lite.db import (
    delete_repository_note,
    get_interview,
    get_latest_interview,
    get_latest_interview_by_role,
    get_relevant_repository_notes,
    get_repository_notes,
    initialize_database,
    list_interview_summaries,
    save_interview,
    save_repository_note,
    save_search_query,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_ROOT = PROJECT_ROOT / "public"


class InterviewRequest(BaseModel):
    role: str = Field(min_length=1)
    answers: dict[str, str]


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    interview_id: str | None = None
    role: str | None = None
    include_repository_notes: bool = True


class RepositoryNoteRequest(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    source: str = Field(min_length=2, max_length=120)
    role: str | None = None
    interview_id: str | None = None
    content: str = Field(min_length=25, max_length=12000)
    attach_latest: bool = False


MIN_ANSWER_CHARS = 80
MAX_ANSWER_CHARS = 2200
MIN_NOTE_CHARS = 25
MAX_NOTE_CHARS = 12000


app = FastAPI(title="LegacyOS Lite", version="0.1.0")
_database_ready = False

def _allowed_origins() -> list[str]:
    env_origins = os.getenv("LEGACYOSLITE_ALLOWED_ORIGINS", "").strip()
    vercel_origin = os.getenv("VERCEL_URL")
    origins = [
        "http://localhost:8010",
        "http://127.0.0.1:8010",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    if vercel_origin:
        origins.append(f"https://{vercel_origin.strip('/')}")
    if env_origins:
        origins.extend(item.strip() for item in env_origins.split(",") if item.strip())
    # Preserve configured origin order while de-duplicating.
    deduped: list[str] = []
    seen = set()
    for origin in origins:
        if origin not in seen:
            deduped.append(origin)
            seen.add(origin)
    return deduped


def _ensure_database_ready() -> None:
    global _database_ready
    if not _database_ready:
        initialize_database()
        _database_ready = True


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def ensure_database_for_api(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        _ensure_database_ready()
    return await call_next(request)


@app.on_event("startup")
def startup() -> None:
    _ensure_database_ready()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(PUBLIC_ROOT / "index.html")


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(PUBLIC_ROOT / "styles.css")


@app.get("/app.js")
def app_script() -> FileResponse:
    return FileResponse(PUBLIC_ROOT / "app.js")


@app.get("/favicon.svg")
def favicon() -> FileResponse:
    return FileResponse(PUBLIC_ROOT / "favicon.svg")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "product": "LegacyOS Lite"}


@app.get("/api/roles")
def roles() -> dict[str, Any]:
    return {
        "roles": [
            {"name": role, "questions": questions}
            for role, questions in ROLE_QUESTIONS.items()
        ]
    }


@app.post("/api/interviews")
def create_interview(payload: InterviewRequest) -> dict[str, Any]:
    role_name = _normalize_role(payload.role)
    if role_name is None:
        raise HTTPException(status_code=400, detail="Unsupported role.")

    required_questions = ROLE_QUESTIONS[role_name]
    cleaned_answers: dict[str, str] = {}
    incomplete_questions: list[str] = []
    short_questions: list[str] = []

    for question in required_questions:
        answer = payload.answers.get(question, "").strip()
        if len(answer) > MAX_ANSWER_CHARS:
            raise HTTPException(
                status_code=400,
                detail=f'Answer for "{question}" exceeds {MAX_ANSWER_CHARS} characters.',
            )
        if not answer:
            incomplete_questions.append(question)
            continue
        if len(answer) < MIN_ANSWER_CHARS:
            short_questions.append(question)
        cleaned_answers[question] = answer

    # Reject unexpected keys to avoid noisy payloads and keep interview replay deterministic.
    unexpected_questions = set(payload.answers.keys()) - set(required_questions)
    if unexpected_questions:
        raise HTTPException(
            status_code=400,
            detail="Interview payload contains unknown prompts. Please resubmit from the current role form.",
        )

    if incomplete_questions or short_questions:
        missing_count = len(incomplete_questions)
        short_count = len(short_questions)
        if missing_count and short_count:
            message = (
                f"Interview quality check failed. {missing_count} unanswered "
                f"and {short_count} below-{MIN_ANSWER_CHARS}-character threshold."
            )
        elif missing_count:
            message = f"Interview quality check failed. {missing_count} required questions are still unanswered."
        else:
            message = f"Interview quality check failed. {short_count} required answers are below {MIN_ANSWER_CHARS} characters."
        raise HTTPException(status_code=400, detail=message)

    generated = generate_interview_package(role_name, cleaned_answers)
    return save_interview(role_name, cleaned_answers, generated)


@app.get("/api/interviews/latest")
def latest_interview(role: str | None = None) -> dict[str, Any]:
    role_name = _normalize_role(role)
    latest = get_latest_interview_by_role(role_name) if role_name else get_latest_interview()
    if latest is None:
        raise HTTPException(status_code=404, detail="No interview found.")
    return latest


@app.get("/api/interviews")
def list_interviews(limit: int = 50) -> dict[str, Any]:
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be at least 1.")
    if limit > 200:
        raise HTTPException(status_code=400, detail="Limit must be 200 or fewer.")
    return {"interviews": list_interview_summaries(limit=limit)}


@app.get("/api/interviews/{interview_id}")
def read_interview(interview_id: str) -> dict[str, Any]:
    try:
        return get_interview(interview_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Interview not found.")


@app.get("/api/graph")
def graph(interview_id: str | None = None, role: str | None = None) -> dict[str, Any]:
    role_name = _normalize_role(role)
    interview = _load_interview_or_latest(interview_id, role_name, allow_stale_fallback=True)
    return _build_graph_payload(interview)


@app.get("/api/graph/export/neo4j")
def export_graph_neo4j(interview_id: str | None = None, role: str | None = None) -> dict[str, Any]:
    role_name = _normalize_role(role)
    interview = _load_interview_or_latest(interview_id, role_name, allow_stale_fallback=True)
    payload = _build_graph_payload(interview)
    return {
        "interview_id": interview["id"],
        "cypher": _build_neo4j_cypher(payload["nodes"], payload["links"]),
        "nodes": payload["nodes"],
        "links": payload["links"],
    }


def _readable_relationship_label(relationship_type: str) -> str:
    return relationship_type.replace("_", " ").title()


def _build_graph_payload(interview: dict[str, Any]) -> dict[str, Any]:
    node_by_id = {entity["id"]: entity for entity in interview["entities"]}
    links = []
    for relationship in interview["relationships"]:
        source = node_by_id.get(relationship["source_id"])
        target = node_by_id.get(relationship["target_id"])
        if source is None or target is None:
            continue
        confidence = relationship.get("confidence", 0.7)
        confidence = float(confidence) if confidence is not None else 0.7
        links.append(
            {
                "id": relationship["id"],
                "source": relationship["source_id"],
                "target": relationship["target_id"],
                "label": relationship["relationship_type"],
                "label_readable": _readable_relationship_label(relationship["relationship_type"]),
                "evidence": relationship["evidence"],
                "strength": max(0.2, min(1.0, round(confidence, 2))),
                "confidence": round(confidence, 2),
                "source_name": source["name"],
                "target_name": target["name"],
            }
        )

    nodes = [
        {
            "id": entity["id"],
            "label": entity["name"],
            "group": entity["entity_type"],
            "confidence": entity["confidence"],
        }
        for entity in interview["entities"]
    ]
    return {
        "interview_id": interview["id"],
        "nodes": nodes,
        "links": links,
    }


def _build_neo4j_cypher(nodes: list[dict[str, Any]], links: list[dict[str, Any]]) -> str:
    def cypher_escape(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace("\"", "\\\"")

    statements = [
        "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;"
    ]
    for node in nodes:
        statements.append(
            "MERGE (n:Entity {id: \""
            + cypher_escape(node["id"])
            + "\"}) SET n.name = \""
            + cypher_escape(node["label"])
            + "\", n.group = \""
            + cypher_escape(node["group"])
            + "\", n.confidence = "
            + str(node["confidence"])
            + ";"
        )
    for link in links:
        rel_label = link["label_readable"].replace(" ", "_").upper()
        statements.append(
            "MATCH (a:Entity {id: \""
            + cypher_escape(link["source"])
            + "\"}), (b:Entity {id: \""
            + cypher_escape(link["target"])
            + "\"}) MERGE (a)-[r:"
            + rel_label
            + "]->(b) SET r.evidence = \""
            + cypher_escape(link["evidence"])
            + "\", r.confidence = "
            + str(link["confidence"])
            + ", r.label = \""
            + cypher_escape(link["label_readable"])
            + "\";"
        )
    return "\n".join(statements)


@app.get("/api/timeline")
def timeline(interview_id: str | None = None, role: str | None = None) -> dict[str, Any]:
    role_name = _normalize_role(role)
    interview = _load_interview_or_latest(interview_id, role_name, allow_stale_fallback=True)
    return {"interview_id": interview["id"], "events": interview["timeline"]}


@app.post("/api/search")
def search(payload: SearchRequest) -> dict[str, Any]:
    role_name = _normalize_role(payload.role)
    interview = _load_interview_or_latest(payload.interview_id, role_name, allow_stale_fallback=True)
    notes = []
    if payload.include_repository_notes:
        notes = get_relevant_repository_notes(
            limit=12,
            interview_id=interview["id"],
            role=interview.get("role"),
        )
    result = answer_question(payload.question, interview, interview["entities"], notes)
    answer = result["answer"] if isinstance(result, dict) else result
    saved = save_search_query(interview["id"], payload.question, answer)
    response: dict[str, Any] = {
        **saved,
        "risk_level": interview["risk_level"],
        "risk_score": interview["risk_score"],
    }
    if isinstance(result, dict):
        response.update(result)
    return response


@app.get("/api/repository/notes")
def list_notes(interview_id: str | None = None, limit: int = 25) -> dict[str, Any]:
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be at least 1.")
    if limit > 200:
        raise HTTPException(status_code=400, detail="Limit must be 200 or fewer.")
    notes = get_repository_notes(limit=limit, interview_id=interview_id)
    return {"notes": notes}


@app.post("/api/repository/notes")
def create_repository_note(payload: RepositoryNoteRequest) -> dict[str, Any]:
    interview_id = payload.interview_id
    role_name = _normalize_role(payload.role)
    if payload.role is not None and role_name is None:
        raise HTTPException(status_code=400, detail="Role is not supported by current role set.")

    if payload.attach_latest and not interview_id:
        latest = get_latest_interview_by_role(role_name) if role_name else get_latest_interview()
        if latest is None:
            raise HTTPException(status_code=400, detail="No interview found to attach notes to.")
        interview_id = latest["id"]

    title = payload.title.strip()
    source = payload.source.strip()
    content = payload.content.strip()
    if len(title) < 3:
        raise HTTPException(status_code=400, detail="title must be at least 3 characters.")
    if len(source) < 2:
        raise HTTPException(status_code=400, detail="source must be at least 2 characters.")
    if len(content) < MIN_NOTE_CHARS:
        raise HTTPException(status_code=400, detail=f"content must be at least {MIN_NOTE_CHARS} characters.")
    if len(content) > MAX_NOTE_CHARS:
        raise HTTPException(status_code=400, detail=f"content must be at most {MAX_NOTE_CHARS} characters.")

    if interview_id:
        try:
            get_interview(interview_id)
        except LookupError as exc:
            if role_name:
                role_latest = get_latest_interview_by_role(role_name)
                if role_latest is not None:
                    interview_id = role_latest["id"]
                else:
                    raise HTTPException(status_code=400, detail="Interview not found for attachment.") from exc
            else:
                raise HTTPException(status_code=400, detail="Interview not found for attachment.") from exc

    return save_repository_note(
        title=title,
        source=source,
        role=role_name,
        interview_id=interview_id,
        content=content,
    )


@app.delete("/api/repository/notes/{note_id}")
def remove_repository_note(note_id: str) -> dict[str, str]:
    removed = delete_repository_note(note_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Repository note not found.")
    return {"status": "removed", "id": note_id}


def _load_interview_or_latest(
    interview_id: str | None,
    role: str | None = None,
    *,
    allow_stale_fallback: bool = False,
) -> dict[str, Any]:
    try:
        if interview_id:
            return get_interview(interview_id)
    except LookupError:
        if not allow_stale_fallback:
            raise HTTPException(status_code=404, detail="Interview not found.")

    try:
        if role:
            role_latest = get_latest_interview_by_role(role)
            if role_latest is not None:
                return role_latest
        latest = get_latest_interview()
        if latest is not None:
            return latest
    except LookupError:
        raise HTTPException(status_code=404, detail="Interview not found.")
    raise HTTPException(status_code=404, detail="No interview found.")


def _normalize_role(role: str | None) -> str | None:
    if not role:
        return None
    normalized = role.strip()
    for candidate in ROLE_QUESTIONS:
        if candidate.lower() == normalized.lower():
            return candidate
    return None

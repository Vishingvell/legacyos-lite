# Copyright (c) 2026 Vishalan Karunanithi
#
# All Rights Reserved.
#
# Unauthorized copying, modification,
# distribution, or commercial use
# is prohibited.

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "legacyoslite.db"


def database_path() -> Path:
    configured = os.getenv("LEGACYOSLITE_DB_PATH")
    return Path(configured).expanduser() if configured else DEFAULT_DB_PATH


def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(row[1]) == column for row in rows)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS interviews (
                id text PRIMARY KEY,
                role text NOT NULL,
                answers_json text NOT NULL,
                summary text NOT NULL,
                profile_json text NOT NULL,
                risk_score integer NOT NULL,
                risk_level text NOT NULL,
                created_at text NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entities (
                id text NOT NULL,
                interview_id text NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
                name text NOT NULL,
                entity_type text NOT NULL,
                confidence real NOT NULL,
                PRIMARY KEY (interview_id, id)
            );

            CREATE TABLE IF NOT EXISTS relationships (
                id text NOT NULL,
                interview_id text NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
                source_entity_id text NOT NULL,
                target_entity_id text NOT NULL,
                relationship_type text NOT NULL,
                evidence text NOT NULL,
                confidence real,
                PRIMARY KEY (interview_id, id)
            );

            CREATE TABLE IF NOT EXISTS timeline_events (
                id text NOT NULL,
                interview_id text NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
                title text NOT NULL,
                event_type text NOT NULL,
                date_label text NOT NULL,
                description text NOT NULL,
                sequence_number integer NOT NULL,
                PRIMARY KEY (interview_id, id)
            );

            CREATE TABLE IF NOT EXISTS search_queries (
                id text PRIMARY KEY,
                interview_id text NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
                question text NOT NULL,
                answer text NOT NULL,
                created_at text NOT NULL
            );

            CREATE TABLE IF NOT EXISTS repository_notes (
                id text PRIMARY KEY,
                interview_id text REFERENCES interviews(id) ON DELETE CASCADE,
                role text,
                source text NOT NULL,
                title text NOT NULL,
                content text NOT NULL,
                created_at text NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_interviews_created_at ON interviews(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_entities_interview ON entities(interview_id);
            CREATE INDEX IF NOT EXISTS idx_relationships_interview ON relationships(interview_id);
            CREATE INDEX IF NOT EXISTS idx_timeline_interview ON timeline_events(interview_id, sequence_number);
            CREATE INDEX IF NOT EXISTS idx_repository_notes_interview ON repository_notes(interview_id);
            CREATE INDEX IF NOT EXISTS idx_repository_notes_created_at ON repository_notes(created_at);
            """
        )
        if not _table_has_column(conn, "relationships", "confidence"):
            conn.execute("ALTER TABLE relationships ADD COLUMN confidence real")
            conn.execute("UPDATE relationships SET confidence = 0.70 WHERE confidence IS NULL")


def save_interview(role: str, answers: dict[str, str], generated: dict[str, Any]) -> dict[str, Any]:
    interview_id = str(uuid4())
    now = _utcnow()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO interviews (
                id, role, answers_json, summary, profile_json, risk_score, risk_level, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interview_id,
                role,
                json.dumps(answers, sort_keys=True),
                generated["summary"],
                json.dumps(generated["profile"], sort_keys=True),
                generated["risk"]["score"],
                generated["risk"]["level"],
                now,
            ),
        )
        for entity in generated["entities"]:
            conn.execute(
                """
                INSERT INTO entities (id, interview_id, name, entity_type, confidence)
                VALUES (?, ?, ?, ?, ?)
                """,
                (entity["id"], interview_id, entity["name"], entity["entity_type"], entity["confidence"]),
            )
        for relationship in generated["relationships"]:
            conn.execute(
                """
                INSERT INTO relationships (
                    id, interview_id, source_entity_id, target_entity_id, relationship_type, evidence, confidence
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relationship["id"],
                    interview_id,
                    relationship["source_id"],
                    relationship["target_id"],
                    relationship["relationship_type"],
                    relationship["evidence"],
                    relationship.get("confidence", 0.70),
                ),
            )
        for event in generated["timeline"]:
            conn.execute(
                """
                INSERT INTO timeline_events (
                    id, interview_id, title, event_type, date_label, description, sequence_number
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    interview_id,
                    event["title"],
                    event["event_type"],
                    event["date_label"],
                    event["description"],
                    event["sequence_number"],
                ),
            )
    return get_interview(interview_id)


def get_latest_interview() -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM interviews ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return get_interview(row["id"]) if row else None


def get_latest_interview_by_role(role: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM interviews
            WHERE lower(role) = lower(?)
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (role,),
        ).fetchone()
    return get_interview(row["id"]) if row else None


def list_interview_summaries(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                interviews.id,
                interviews.role,
                interviews.summary,
                interviews.profile_json,
                interviews.risk_score,
                interviews.risk_level,
                interviews.created_at,
                COUNT(entities.id) AS entity_count
            FROM interviews
            LEFT JOIN entities ON entities.interview_id = interviews.id
            GROUP BY interviews.id
            ORDER BY interviews.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    summaries = []
    for row in rows:
        profile = json.loads(row["profile_json"])
        summaries.append(
            {
                "id": row["id"],
                "role": row["role"],
                "summary": row["summary"],
                "risk_score": row["risk_score"],
                "risk_level": row["risk_level"],
                "created_at": row["created_at"],
                "coverage": profile.get("coverage", "Starter"),
                "top_entities": profile.get("top_entities", [])[:5],
                "entity_count": row["entity_count"],
            }
        )
    return summaries


def get_interview(interview_id: str) -> dict[str, Any]:
    with connect() as conn:
        interview = conn.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,)).fetchone()
        if interview is None:
            raise LookupError("Interview not found.")
        entities = conn.execute(
            "SELECT id, name, entity_type, confidence FROM entities WHERE interview_id = ? ORDER BY confidence DESC, name",
            (interview_id,),
        ).fetchall()
        relationships = conn.execute(
            """
            SELECT id, source_entity_id, target_entity_id, relationship_type, evidence, confidence
            FROM relationships
            WHERE interview_id = ?
            """,
            (interview_id,),
        ).fetchall()
        timeline = conn.execute(
            """
            SELECT id, title, event_type, date_label, description, sequence_number
            FROM timeline_events
            WHERE interview_id = ?
            ORDER BY sequence_number
            """,
            (interview_id,),
        ).fetchall()

    return {
        "id": interview["id"],
        "role": interview["role"],
        "answers": json.loads(interview["answers_json"]),
        "summary": interview["summary"],
        "profile": json.loads(interview["profile_json"]),
        "risk_score": interview["risk_score"],
        "risk_level": interview["risk_level"],
        "created_at": interview["created_at"],
        "entities": [dict(row) for row in entities],
        "relationships": [
            {
                "id": row["id"],
                "source_id": row["source_entity_id"],
                "target_id": row["target_entity_id"],
                "relationship_type": row["relationship_type"],
                "evidence": row["evidence"],
                "confidence": row["confidence"] if row["confidence"] is not None else 0.70,
            }
            for row in relationships
        ],
        "timeline": [dict(row) for row in timeline],
    }


def save_search_query(interview_id: str, question: str, answer: str) -> dict[str, str]:
    query_id = str(uuid4())
    created_at = _utcnow()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO search_queries (id, interview_id, question, answer, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (query_id, interview_id, question, answer, created_at),
        )
    return {"id": query_id, "interview_id": interview_id, "question": question, "answer": answer, "created_at": created_at}


def save_repository_note(
    *,
    title: str,
    source: str,
    role: str | None,
    interview_id: str | None,
    content: str,
) -> dict[str, Any]:
    note_id = str(uuid4())
    created_at = _utcnow()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO repository_notes (
                id, interview_id, role, source, title, content, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (note_id, interview_id, role, source, title, content, created_at),
        )
    return {
        "id": note_id,
        "interview_id": interview_id,
        "role": role,
        "source": source,
        "title": title,
        "content": content,
        "created_at": created_at,
    }


def get_repository_notes(limit: int = 25, interview_id: str | None = None) -> list[dict[str, Any]]:
    with connect() as conn:
        if interview_id is None:
            rows = conn.execute(
                """
                SELECT id, interview_id, role, source, title, content, created_at
                FROM repository_notes
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, interview_id, role, source, title, content, created_at
                FROM repository_notes
                WHERE interview_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (interview_id, limit),
            ).fetchall()
    return [dict(row) for row in rows]


def get_relevant_repository_notes(
    *,
    limit: int = 25,
    interview_id: str | None = None,
    role: str | None = None,
) -> list[dict[str, Any]]:
    with connect() as conn:
        if interview_id is not None and role is not None:
            rows = conn.execute(
                """
                SELECT id, interview_id, role, source, title, content, created_at
                FROM repository_notes
                WHERE interview_id = ?
                   OR lower(role) = lower(?)
                   OR role IS NULL
                ORDER BY
                    CASE
                        WHEN interview_id = ? THEN 0
                        WHEN lower(role) = lower(?) THEN 1
                        ELSE 2
                    END,
                    created_at DESC
                LIMIT ?
                """,
                (interview_id, role, interview_id, role, limit),
            ).fetchall()
        elif interview_id is not None:
            rows = conn.execute(
                """
                SELECT id, interview_id, role, source, title, content, created_at
                FROM repository_notes
                WHERE interview_id = ? OR role IS NULL
                ORDER BY CASE WHEN interview_id = ? THEN 0 ELSE 1 END, created_at DESC
                LIMIT ?
                """,
                (interview_id, interview_id, limit),
            ).fetchall()
        elif role is not None:
            rows = conn.execute(
                """
                SELECT id, interview_id, role, source, title, content, created_at
                FROM repository_notes
                WHERE lower(role) = lower(?) OR role IS NULL
                ORDER BY CASE WHEN lower(role) = lower(?) THEN 0 ELSE 1 END, created_at DESC
                LIMIT ?
                """,
                (role, role, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, interview_id, role, source, title, content, created_at
                FROM repository_notes
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def delete_repository_note(note_id: str) -> bool:
    with connect() as conn:
        result = conn.execute("DELETE FROM repository_notes WHERE id = ?", (note_id,))
        return result.rowcount > 0


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

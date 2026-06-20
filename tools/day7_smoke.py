#!/usr/bin/env python3
"""Lightweight Day 7 smoke checks for LegacyOS Lite."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class SmokeError(RuntimeError):
    pass


ROOT_DIR = Path(__file__).resolve().parents[1]
PORT = int(os.getenv("LEGACYOSLITE_SMOKE_PORT", "8011"))
DB_PATH = ROOT_DIR / "data" / "legacyoslite.smoke.db"


def _url(path: str) -> str:
    return f"http://127.0.0.1:{PORT}{path}"


def _request(
    path: str,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        _url(path),
        data=payload,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SmokeError(f"{method} {path} failed ({exc.code}): {detail.strip()}") from exc
    except urllib.error.URLError as exc:
        raise SmokeError(f"Unable to reach {_url(path)}: {exc}") from exc

    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"Invalid JSON from {path}: {raw[:180]!r}") from exc


def _wait_for_api() -> None:
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        try:
            health = _request("/api/health")
            if health.get("status") == "ok":
                return
        except SmokeError:
            time.sleep(0.2)
    raise SmokeError("Timed out waiting for API health endpoint.")


def run() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR / "backend")
    env["LEGACYOSLITE_DB_PATH"] = str(DB_PATH)
    DB_PATH.unlink(missing_ok=True)

    uvicorn_bin = ROOT_DIR.parent / ".venv" / "bin" / "uvicorn"
    if not uvicorn_bin.exists():
        raise SmokeError("Could not locate .venv/bin/uvicorn. Install dependencies first.")

    print(f"Starting LegacyOS Lite smoke server on 127.0.0.1:{PORT} ...")
    process = subprocess.Popen(
        [
            str(uvicorn_bin),
            "legacyos_lite.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=ROOT_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_api()
        health = _request("/api/health")
        assert health.get("status") == "ok"
        assert health.get("product") == "LegacyOS Lite"

        roles_payload = _request("/api/roles")
        roles = roles_payload.get("roles", [])
        if len(roles) < 4:
            raise SmokeError("Expected at least 4 roles in /api/roles.")
        role = roles[0]
        role_name = role["name"]
        questions = role["questions"]

        answer_text = (
            "This is a long enough interview response for the question so the risk engine "
            "and extraction routines can evaluate it with usable context."
        )
        answers = {question: answer_text for question in questions}
        interview = _request(
            "/api/interviews",
            method="POST",
            body={"role": role_name, "answers": answers},
        )

        interview_id = interview["id"]
        if not isinstance(interview_id, str):
            raise SmokeError("Interview response missing valid id.")

        graph = _request(f"/api/graph?interview_id={interview_id}")
        timeline = _request(f"/api/timeline?interview_id={interview_id}")
        _request(
            "/api/repository/notes",
            method="POST",
            body={
                "title": "Day 7 smoke note",
                "source": "Demo run",
                "role": role_name,
                "content": "This is a sample operational note used in day 7 smoke verification.",
                "attach_latest": True,
            },
        )
        notes = _request(f"/api/repository/notes?interview_id={interview_id}&limit=5")
        if not notes.get("notes"):
            raise SmokeError("Expected at least one repository note.")

        search = _request(
            "/api/search",
            method="POST",
            body={
                "question": "What are the top continuity risks from this profile?",
                "include_repository_notes": True,
            },
        )
        if not search.get("answer"):
            raise SmokeError("Search did not return an answer.")

        latest = _request(f"/api/interviews/{interview_id}")
        if latest.get("role") != role_name:
            raise SmokeError("Retrieved interview role mismatch.")

        print("Smoke checks: PASS")
        print(f"Interview: {interview_id}")
        print(f"Role: {role_name}")
        print(f"Risk: {interview.get('risk_score')}/100 ({interview.get('risk_level')})")
        print(f"Graph nodes: {len(graph.get('nodes', []))}")
        print(f"Timeline events: {len(timeline.get('events', []))}")
        print(f"Repository notes: {len(notes.get('notes', []))}")
        print(f"Search answer chars: {len(search.get('answer', ''))}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        try:
            DB_PATH.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> int:
    try:
        run()
        return 0
    except SmokeError as exc:
        print(f"Smoke checks: FAIL\n{exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Smoke checks: ERROR\n{exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

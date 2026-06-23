#!/usr/bin/env python3
# Copyright (c) 2026 Vishalan Karunanithi.
# All Rights Reserved.
# This repository is published for hackathon review only. No permission is granted to copy,
# modify, distribute, sublicense, or commercially use this software without written permission.

"""Verify LegacyOS Lite search keeps role evidence scoped and inspectable."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "legacyoslite.search-scope.db"
sys.path.insert(0, str(ROOT_DIR / "backend"))
os.environ["LEGACYOSLITE_DB_PATH"] = str(DB_PATH)
os.environ["LEGACYOSLITE_SEED_DEMO_DATA"] = "false"

from fastapi.testclient import TestClient  # noqa: E402
from legacyos_lite.ai import ROLE_QUESTIONS  # noqa: E402
from legacyos_lite.main import app  # noqa: E402


def answers_for(role: str, sentences: list[str]) -> dict[str, str]:
    return dict(zip(ROLE_QUESTIONS[role], sentences))


def create_interview(client: TestClient, role: str, sentences: list[str]) -> dict[str, Any]:
    response = client.post(
        "/api/interviews",
        json={"role": role, "answers": answers_for(role, sentences)},
    )
    response.raise_for_status()
    return response.json()


def add_note(client: TestClient, role: str, interview_id: str, title: str, content: str) -> None:
    response = client.post(
        "/api/repository/notes",
        json={
            "title": title,
            "source": f"{role} review note",
            "role": role,
            "interview_id": interview_id,
            "content": content,
        },
    )
    response.raise_for_status()


def ask(
    client: TestClient,
    active_interview: dict[str, Any],
    question: str,
    expected_role: str,
    expected_source: str,
    forbidden_source: str,
) -> None:
    response = client.post(
        "/api/search",
        json={
            "question": question,
            "interview_id": active_interview["id"],
            "role": active_interview["role"],
            "include_repository_notes": True,
        },
    )
    response.raise_for_status()
    payload = response.json()
    source_titles = [source["title"] for source in payload.get("source_summary", [])]
    selected_role = payload.get("selected_role")
    if selected_role != expected_role:
        raise AssertionError(f"Expected {expected_role}, got {selected_role}: {payload}")
    if expected_source not in source_titles:
        raise AssertionError(f"Missing source {expected_source}: {source_titles}")
    if forbidden_source in source_titles:
        raise AssertionError(f"Leaked source {forbidden_source}: {source_titles}")
    print(f"PASS {expected_role}: {question}")
    print(f"  sources: {', '.join(source_titles)}")


def main() -> int:
    DB_PATH.unlink(missing_ok=True)
    client = TestClient(app)

    cloud = create_interview(
        client,
        "Cloud Engineer",
        [
            "I own AWS production accounts, CloudFront distributions, S3 dashboard assets, IAM deployment roles, and GitHub Actions pipelines for frontend releases.",
            "Deployment verification, CloudFront invalidation, rollback checks, and release health dashboards slow down when the Cloud Engineer is unavailable.",
            "A replacement should first understand stale CloudFront cache incidents, expired AWS role sessions, and failed invalidation checks after deployment.",
            "The most important documentation is the CloudFront release runbook, deployment checklist, rollback screenshots, and repository incident notes.",
            "The frontend lead, DevOps backup, and security engineer depend on this cloud release knowledge during production incidents.",
        ],
    )
    soc = create_interview(
        client,
        "SOC Analyst",
        [
            "I monitor SIEM alerts, IAM audit events, service account activity, and GitHub workflow logs for deployment security investigations.",
            "Initial triage preserves evidence, checks timestamps, compares activity with approved CI/CD windows, and escalates suspicious service account behavior.",
            "The next analyst should focus on CI/CD false positives, privilege wording, noisy SIEM alerts, and missing workflow run IDs.",
            "Mandatory playbooks preserve SIEM events, collect IAM evidence, document containment decisions, and clarify escalation ownership.",
            "Security engineering and the application developer cover handover when suspicious automation needs review across shifts.",
        ],
    )
    sysadmin = create_interview(
        client,
        "System Administrator",
        [
            "I operate DNS records, VPN access, Linux server patching, backup verification, identity groups, and emergency admin recovery procedures.",
            "Patch windows, DNS change review, backup restoration checks, and VPN access recovery would slow down without the administrator runbook.",
            "A replacement should understand failed patch rollbacks, stale DNS entries, backup restore order, and identity escalation paths.",
            "Server inventories, config baselines, DNS change logs, and backup runbooks are stored in the infrastructure documentation area.",
            "The service desk, infrastructure lead, and emergency access approver depend on this administration knowledge during outages.",
        ],
    )

    add_note(
        client,
        "Cloud Engineer",
        cloud["id"],
        "CloudFront cache incident review",
        "Customers saw outdated dashboard assets because CloudFront cache invalidation was skipped after deployment. The fix was to rotate the expired AWS role session, manually invalidate CloudFront paths, and add release validation to the pipeline.",
    )
    add_note(
        client,
        "SOC Analyst",
        soc["id"],
        "SOC false positive incident review",
        "The SOC alert was a false positive after five hours because service account activity came from approved CI/CD automation, not attacker activity. Evidence came from SIEM events, IAM audit logs, and GitHub workflow run IDs.",
    )
    add_note(
        client,
        "System Administrator",
        sysadmin["id"],
        "DNS rollback outage review",
        "A DNS rollback outage was resolved by restoring the previous zone file, validating VPN access, checking backup records, and documenting emergency approval steps for administrators.",
    )

    ask(
        client,
        active_interview=soc,
        question="Why did customers see outdated dashboard assets after the CloudFront deployment?",
        expected_role="Cloud Engineer",
        expected_source="CloudFront cache incident review",
        forbidden_source="SOC false positive incident review",
    )
    ask(
        client,
        active_interview=cloud,
        question="Why was the SOC alert confirmed as a false positive?",
        expected_role="SOC Analyst",
        expected_source="SOC false positive incident review",
        forbidden_source="CloudFront cache incident review",
    )
    ask(
        client,
        active_interview=cloud,
        question="What fixed the DNS rollback outage for VPN access?",
        expected_role="System Administrator",
        expected_source="DNS rollback outage review",
        forbidden_source="CloudFront cache incident review",
    )

    DB_PATH.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

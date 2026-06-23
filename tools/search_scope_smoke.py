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
KEEP_DB = os.getenv("LEGACYOSLITE_SEARCH_SCOPE_KEEP_DB", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
sys.path.insert(0, str(ROOT_DIR / "backend"))
os.environ["LEGACYOSLITE_DB_PATH"] = str(DB_PATH)
os.environ["LEGACYOSLITE_SEED_DEMO_DATA"] = "false"

from fastapi.testclient import TestClient  # noqa: E402
from legacyos_lite.ai import ROLE_QUESTIONS  # noqa: E402
from legacyos_lite.main import app  # noqa: E402


PROFILE_ANSWERS: dict[str, list[str]] = {
    "Cloud Engineer": [
        "I own AWS production accounts, CloudFront distributions, S3 dashboard assets, IAM deployment roles, and GitHub Actions pipelines for frontend releases.",
        "Deployment verification, CloudFront invalidation, rollback checks, and release health dashboards slow down when the Cloud Engineer is unavailable.",
        "A replacement should first understand stale CloudFront cache incidents, expired AWS role sessions, and failed invalidation checks after deployment.",
        "The most important documentation is the CloudFront release runbook, deployment checklist, rollback screenshots, and repository incident notes.",
        "The frontend lead, DevOps backup, and security engineer depend on this cloud release knowledge during production incidents.",
    ],
    "SOC Analyst": [
        "I monitor SIEM alerts, IAM audit events, service account activity, and GitHub workflow logs for deployment security investigations.",
        "Initial triage preserves evidence, checks timestamps, compares activity with approved CI/CD windows, and escalates suspicious service account behavior.",
        "The next analyst should focus on CI/CD false positives, privilege wording, noisy SIEM alerts, and missing workflow run IDs.",
        "Mandatory playbooks preserve SIEM events, collect IAM evidence, document containment decisions, and clarify escalation ownership.",
        "Security engineering and the application developer cover handover when suspicious automation needs review across shifts.",
    ],
    "System Administrator": [
        "I operate DNS records, VPN access, Linux server patching, backup verification, identity groups, and emergency admin recovery procedures.",
        "Patch windows, DNS change review, backup restoration checks, and VPN access recovery would slow down without the administrator runbook.",
        "A replacement should understand failed patch rollbacks, stale DNS entries, backup restore order, and identity escalation paths.",
        "Server inventories, config baselines, DNS change logs, and backup runbooks are stored in the infrastructure documentation area.",
        "The service desk, infrastructure lead, and emergency access approver depend on this administration knowledge during outages.",
    ],
    "Software Developer": [
        "I maintain the customer API, queue worker, token refresh code, release branch, and dashboard integration services used by internal teams.",
        "Debugging memory growth, worker retries, token refresh failures, and rollback validation slows down without developer repository context.",
        "A replacement should understand the memory leak investigation, queue backpressure, token cache behavior, and hidden retry assumptions.",
        "Architecture notes, pull request decisions, code comments, and runbook snippets are stored in the developer knowledge repository.",
        "The product owner, QA engineer, cloud engineer, and support lead depend on this implementation knowledge during customer incidents.",
    ],
    "Security Engineer": [
        "I own WAF rules, vulnerability exceptions, policy reviews, compliance evidence, and security control tuning for exposed applications.",
        "Exception approvals, compensating control checks, vulnerability triage, and WAF rollout validation slow down without security context.",
        "A successor should understand temporary WAF bypasses, vulnerability acceptance windows, compensating controls, and policy sign-off history.",
        "Security policies, exception records, evidence folders, audit notes, and control review decisions are kept in the repository.",
        "SOC, cloud engineering, application developers, and audit reviewers depend on this security exception knowledge.",
    ],
    "Dietician": [
        "I manage renal diet plans, allergy substitutions, kitchen handoff notes, nutrition screening, and clinical diet review workflows.",
        "Patient meal substitutions, contraindication checks, allergy review, and ward handoff decisions slow down when dietician context is missing.",
        "The next dietician should understand texture-modified diet substitutions, allergy warnings, renal potassium limits, and escalation paths.",
        "Diet protocols, kitchen substitution notes, patient care plan excerpts, and audit records are kept in the nutrition repository.",
        "Nurses, kitchen supervisors, physicians, and patient care coordinators depend on this dietician knowledge during meal changes.",
    ],
    "Manager": [
        "I coordinate delivery rituals, stakeholder updates, approval meetings, vendor check-ins, and operating reviews across several teams.",
        "Planning decisions, escalation timing, stakeholder tradeoffs, and approval follow-up slow down when manager context is missing.",
        "A successor should understand dependency risks, delivery promises, recurring escalation paths, and which decisions were already reviewed.",
        "Plans, metrics, decision logs, vendor notes, and operating documents are stored in the management repository area.",
        "Team leads, vendors, executives, and delivery owners depend on this management context during handover or incident review.",
    ],
}


REPOSITORY_NOTES: list[dict[str, str]] = [
    {
        "role": "Cloud Engineer",
        "title": "CloudFront cache incident review",
        "content": "Customers saw outdated dashboard assets because CloudFront cache invalidation was skipped after deployment. The fix was to rotate the expired AWS role session, manually invalidate CloudFront paths, and add release validation to the pipeline.",
    },
    {
        "role": "SOC Analyst",
        "title": "SOC false positive incident review",
        "content": "The SOC alert was a false positive after five hours because service account activity came from approved CI/CD automation, not attacker activity. Evidence came from SIEM events, IAM audit logs, and GitHub workflow run IDs.",
    },
    {
        "role": "System Administrator",
        "title": "DNS rollback outage review",
        "content": "A DNS rollback outage was resolved by restoring the previous zone file, validating VPN access, checking backup records, and documenting emergency approval steps for administrators.",
    },
    {
        "role": "Software Developer",
        "title": "API worker memory leak review",
        "content": "The API worker memory leak came from a token refresh cache that retained queue job payloads after retries. The developer fixed it by clearing stale token objects, adding heap snapshots, and documenting the rollback path.",
    },
    {
        "role": "Security Engineer",
        "title": "WAF exception review",
        "content": "The WAF vulnerability exception was approved for seven days only because compensating controls blocked risky request paths. The Security Engineer documented the policy approval, evidence folder, and required review date.",
    },
    {
        "role": "Dietician",
        "title": "Allergy substitution handoff",
        "content": "A patient allergy substitution was escalated because the kitchen proposed a soy-based replacement for a renal diet plan. The Dietician documented the safe substitute, kitchen handoff, and nursing confirmation step.",
    },
]


SCENARIOS: list[dict[str, str]] = [
    {
        "active_role": "SOC Analyst",
        "question": "Why did customers see outdated dashboard assets after the CloudFront deployment?",
        "expected_role": "Cloud Engineer",
        "expected_source": "CloudFront cache incident review",
    },
    {
        "active_role": "Cloud Engineer",
        "question": "Why was the SOC alert confirmed as a false positive?",
        "expected_role": "SOC Analyst",
        "expected_source": "SOC false positive incident review",
    },
    {
        "active_role": "Cloud Engineer",
        "question": "What fixed the DNS rollback outage for VPN access?",
        "expected_role": "System Administrator",
        "expected_source": "DNS rollback outage review",
    },
    {
        "active_role": "Security Engineer",
        "question": "What caused the API worker memory leak around token refresh jobs?",
        "expected_role": "Software Developer",
        "expected_source": "API worker memory leak review",
    },
    {
        "active_role": "Software Developer",
        "question": "Why was the WAF vulnerability exception approved only temporarily?",
        "expected_role": "Security Engineer",
        "expected_source": "WAF exception review",
    },
    {
        "active_role": "Manager",
        "question": "Which allergy substitution was escalated for the renal diet patient?",
        "expected_role": "Dietician",
        "expected_source": "Allergy substitution handoff",
    },
]


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
    interviews: dict[str, dict[str, Any]],
    scenario: dict[str, str],
    all_source_titles: set[str],
) -> dict[str, Any]:
    active_interview = interviews[scenario["active_role"]]
    response = client.post(
        "/api/search",
        json={
            "question": scenario["question"],
            "interview_id": active_interview["id"],
            "role": active_interview["role"],
            "include_repository_notes": True,
        },
    )
    response.raise_for_status()
    payload = response.json()
    source_titles = [source["title"] for source in payload.get("source_summary", [])]
    expected_source = scenario["expected_source"]
    leaked_sources = sorted((all_source_titles - {expected_source}).intersection(source_titles))

    if payload.get("selected_role") != scenario["expected_role"]:
        raise AssertionError(f"Expected {scenario['expected_role']}, got {payload.get('selected_role')}: {payload}")
    if expected_source not in source_titles:
        raise AssertionError(f"Missing source {expected_source}: {source_titles}")
    if leaked_sources:
        raise AssertionError(f"Leaked unrelated sources {leaked_sources}: {source_titles}")

    return {
        "question": scenario["question"],
        "active_role": scenario["active_role"],
        "selected_role": payload["selected_role"],
        "source": expected_source,
        "answer_preview": " ".join(str(payload.get("answer", "")).split())[:120],
    }


def main() -> int:
    DB_PATH.unlink(missing_ok=True)
    client = TestClient(app)

    interviews = {
        role: create_interview(client, role, answers)
        for role, answers in PROFILE_ANSWERS.items()
    }
    all_source_titles = {note["title"] for note in REPOSITORY_NOTES}

    for note in REPOSITORY_NOTES:
        role = note["role"]
        add_note(client, role, interviews[role]["id"], note["title"], note["content"])

    results = [ask(client, interviews, scenario, all_source_titles) for scenario in SCENARIOS]

    print("| Question | Active profile | Profile used | Evidence source |")
    print("|---|---|---|---|")
    for result in results:
        print(
            "| "
            + " | ".join(
                [
                    result["question"],
                    result["active_role"],
                    result["selected_role"],
                    result["source"],
                ]
            )
            + " |"
        )

    if KEEP_DB:
        print(f"\nKept search-scope database at {DB_PATH}")
    else:
        DB_PATH.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

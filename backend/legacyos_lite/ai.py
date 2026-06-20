# Copyright (c) 2026 Vishalan Karunanithi.
# All Rights Reserved.
# This repository is published for hackathon review only. No permission is granted to copy,
# modify, distribute, sublicense, or commercially use this software without written permission.

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from urllib import error as _url_error
from urllib import request as _url_request
from hashlib import sha256
from typing import Any


ROLE_QUESTIONS: dict[str, list[str]] = {
    "Cloud Engineer": [
        "Which cloud platforms, services, and environments do you own or regularly support?",
        "What production workflows or deployments would slow down if you were unavailable?",
        "Which incidents, outages, or recurring risks should a replacement understand first?",
        "Where is the most important documentation, automation, or runbook material located?",
        "Who depends on your knowledge and who can partially cover your responsibilities?",
    ],
    "SOC Analyst": [
        "Which SIEM/SOAR tools and alert sources are your core daily monitoring assets?",
        "How do you triage alerts from raw signal to confirmed investigation in your first 30 minutes?",
        "Which attack patterns, false positives, and blind spots should the next analyst focus on?",
        "Which containment, escalation, and evidence-collection playbooks are mandatory during incidents?",
        "Who covers shift handover, and what context must never be lost at changeover?",
    ],
    "System Administrator": [
        "Which infrastructure systems and services do you operate (Identity, DNS, AD, patching, backups)?",
        "What are the most failure-prone services, and how should on-call prioritize recovery?",
        "Which maintenance, change-control, and runbook workflows must always continue without gap?",
        "Where are server inventories, config baselines, and automation scripts kept and reviewed?",
        "Who can temporarily cover access requests, patching, and emergency remediation?",
    ],
    "Security Engineer": [
        "Which controls, tools, alerts, and response workflows do you own or regularly tune?",
        "What security incidents or investigations taught the team the most important lessons?",
        "Which risks are under-documented, manually handled, or dependent on your judgment?",
        "Where are playbooks, evidence, policies, or compliance notes maintained?",
        "Who relies on your security knowledge during escalations or audits?",
    ],
    "Software Developer": [
        "Which products, services, repositories, and critical code paths do you know best?",
        "What release, rollback, debugging, or on-call workflows depend on your context?",
        "Which technical debt, failure modes, or hidden assumptions should the team know?",
        "Where are architecture notes, decisions, diagrams, or runbooks stored?",
        "Who reviews, maintains, or depends on your systems and implementation knowledge?",
    ],
    "Dietician": [
        "Which nutrition programs, patient care pathways, and clinical systems do you own most?",
        "How do you handle substitutions, contraindications, and escalation in care planning?",
        "Where do you keep diet protocols, guidelines, audits, and compliance notes?",
        "Which handoff points create risk when context is missing between shifts or teams?",
        "Who are the key stakeholders you depend on for safe, effective patient guidance?",
    ],
    "Manager": [
        "Which teams, rituals, programs, vendors, and stakeholder workflows do you coordinate?",
        "What decisions, tradeoffs, or historical context should a successor understand?",
        "Which people dependencies, delivery risks, or escalation patterns are under-documented?",
        "Where are plans, metrics, decision logs, and operating documents maintained?",
        "Who depends on your coordination, approvals, or institutional context?",
    ],
}


ENTITY_KEYWORDS: dict[str, set[str]] = {
    "System": {
        "ad",
        "active directory",
        "linux",
        "windows",
        "dns",
        "dhcp",
        "vpn",
        "patch",
        "server",
        "aws",
        "azure",
        "gcp",
        "kubernetes",
        "eks",
        "terraform",
        "jenkins",
        "github",
        "gitlab",
        "postgres",
        "redis",
        "emr",
        "ehr",
        "splunk",
        "datadog",
        "siem",
        "iam",
        "okta",
        "pagerduty",
        "service",
        "repository",
        "pipeline",
        "cluster",
        "database",
    },
    "Risk": {
        "risk",
        "manual",
        "undocumented",
        "single point",
        "outage",
        "incident",
        "unknown",
        "fragile",
        "blocked",
        "deprecated",
        "compliance",
        "approval",
        "escalation",
    },
    "Process": {
        "deployment",
        "rollback",
        "release",
        "review",
        "audit",
        "on-call",
        "oncall",
        "runbook",
        "playbook",
        "handoff",
        "triage",
        "migration",
        "change",
    },
    "Knowledge Source": {
        "docs",
        "documentation",
        "notion",
        "confluence",
        "runbook",
        "diagram",
        "decision log",
        "ticket",
        "wiki",
        "slack",
        "meal plan",
        "nutrition",
        "patient",
        "care plan",
    },
    "Person or Team": {
        "team",
        "manager",
        "engineer",
        "security",
        "developer",
        "sre",
        "platform",
        "ops",
        "stakeholder",
        "vendor",
    },
}

OLLAMA_ENABLED = os.getenv("LEGACYOSLITE_USE_OLLAMA", "0").strip().lower() in {"1", "true", "yes", "on"}
OLLAMA_BASE_URL = os.getenv("LEGACYOSLITE_OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("LEGACYOSLITE_OLLAMA_MODEL", "llama3.2")
try:
    OLLAMA_TIMEOUT = max(2, int(os.getenv("LEGACYOSLITE_OLLAMA_TIMEOUT", "8")))
except ValueError:
    OLLAMA_TIMEOUT = 8

_STOP_WORDS = {
    "the", "and", "or", "for", "with", "that", "this", "are", "was", "were", "you", "your",
    "have", "has", "had", "their", "there", "what", "where", "when", "which", "while", "will",
    "would", "should", "could", "might", "about", "from", "into", "been", "were", "about",
    "under", "after", "before", "between", "through", "during", "into", "about", "again", "other",
}


@dataclass(frozen=True)
class GeneratedEntity:
    id: str
    name: str
    entity_type: str
    confidence: float


@dataclass(frozen=True)
class GeneratedRelationship:
    id: str
    source_id: str
    target_id: str
    relationship_type: str
    evidence: str
    confidence: float


@dataclass(frozen=True)
class GeneratedTimelineEvent:
    id: str
    title: str
    event_type: str
    date_label: str
    description: str
    sequence_number: int


def generate_interview_package(role: str, answers: dict[str, str]) -> dict[str, Any]:
    clean_answers = {key: value.strip() for key, value in answers.items() if value.strip()}
    answer_text = "\n".join(clean_answers.values())
    entities = _extract_entities(role, answer_text)
    relationships = _build_relationships(role, entities, answer_text)
    timeline = _build_timeline(role, clean_answers, answer_text)
    risk = _score_risk(role, clean_answers, entities)

    return {
        "summary": _summarize(role, clean_answers, entities, risk),
        "profile": {
            "role": role,
            "coverage": _coverage_label(clean_answers),
            "top_entities": [entity.name for entity in entities if entity.entity_type != "Role"][:8],
            "critical_dependencies": [
                entity.name for entity in entities if entity.entity_type in {"System", "Person or Team"}
            ][:6],
            "risk_drivers": risk["drivers"],
            "risk_score": risk["score"],
            "risk_breakdown": risk["breakdown"],
            "risk_level": risk["level"],
            "recommended_actions": _recommend_actions(risk["level"], entities, risk["breakdown"]),
        },
        "entities": [entity.__dict__ for entity in entities],
        "relationships": [relationship.__dict__ for relationship in relationships],
        "timeline": [event.__dict__ for event in timeline],
        "risk": risk,
    }


def answer_question(
    question: str,
    interview: dict[str, Any],
    entities: list[dict[str, Any]],
    repository_notes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_question = question.lower().strip()
    if not normalized_question:
        return {
            "answer": "No question was provided.",
            "source_summary": [],
            "model": "rule",
            "answer_style": "empty-input",
        }

    summary = interview.get("summary", "")
    profile = interview.get("profile", {})
    risk_score = interview.get("risk_score")
    risk_level = interview.get("risk_level")
    answer_bank = " ".join(interview.get("answers", {}).values())
    timeline_events = interview.get("timeline", [])

    interview_source: dict[str, Any] = {
        "kind": "interview",
        "title": f"{interview.get('role', 'Interview')} profile",
        "excerpt": _sentence_preview(summary, 30),
        "content": summary,
    }

    matched_entities = [
        entity["name"]
        for entity in entities
        if entity["name"].lower() in normalized_question or any(part in normalized_question for part in entity["name"].lower().split())
    ][:5]

    note_hits = _rank_repository_notes(normalized_question, repository_notes or [])
    note_sources = [_repository_note_source(note) for note in note_hits[:3]]
    interview_sources = [interview_source]

    asks_about_risk = any(term in normalized_question for term in ("risk", "score", "exposure"))
    asks_about_dependency = any(term in normalized_question for term in ("who", "depend", "dependency", "people", "team"))
    repository_first_terms = {
        "incident",
        "false",
        "positive",
        "why",
        "cause",
        "root",
        "happened",
        "investigation",
        "digging",
    }

    if asks_about_risk:
        if note_hits:
            include_profile_context = _note_belongs_to_interview_context(note_hits[0], interview)
            profile_context = (risk_level, risk_score) if include_profile_context else (None, None)
            return {
                "answer": _repository_risk_answer(note_hits[0], profile_context[0], profile_context[1]),
                "source_summary": _repository_grounded_sources(note_sources, interview_source, include_profile_context),
                "model": "rule",
                "answer_style": "repository-risk-summary",
            }
        drivers = ", ".join(profile.get("risk_drivers", [])[:4]) or "limited documentation signals"
        return {
            "answer": f"Current risk is {risk_level} at {risk_score}/100. Main drivers: {drivers}.",
            "source_summary": interview_sources,
            "model": "rule",
            "answer_style": "risk-summary",
        }

    if asks_about_dependency:
        if note_hits:
            include_profile_context = _note_belongs_to_interview_context(note_hits[0], interview)
            profile_context = profile if include_profile_context else {}
            entity_context = entities if include_profile_context else []
            return {
                "answer": _repository_dependency_answer(note_hits[0], profile_context, entity_context),
                "source_summary": _repository_grounded_sources(note_sources, interview_source, include_profile_context),
                "model": "rule",
                "answer_style": "repository-dependency-summary",
            }
        dependencies = ", ".join(profile.get("critical_dependencies", [])[:5])
        if not dependencies:
            dependencies = ", ".join(_infer_entity_mentions(entities, normalized_question, limit=5)) or "not yet clear from this interview"
        return {
            "answer": f"Primary dependency signals are: {dependencies}.",
            "source_summary": interview_sources,
            "model": "rule",
            "answer_style": "dependency-summary",
        }

    if note_hits and any(term in normalized_question for term in repository_first_terms):
        include_profile_context = _note_belongs_to_interview_context(note_hits[0], interview)
        timeline_context = timeline_events if include_profile_context else []
        return {
            "answer": _repository_incident_answer(note_hits[0], timeline_context),
            "source_summary": _repository_grounded_sources(note_sources, interview_source, include_profile_context),
            "model": "rule",
            "answer_style": "repository-incident-summary",
        }

    if OLLAMA_ENABLED:
        generated = _answer_with_ollama(
            question=question,
            role=interview.get("role", "team member"),
            summary=summary,
            profile=profile,
            timeline_events=timeline_events,
            entities=entities,
            repository_notes=note_hits,
        )
        if generated:
            return {
                "answer": generated,
                "source_summary": note_sources or interview_sources,
                "model": "ollama",
                "answer_style": "llm-powered",
            }

    if "timeline" in normalized_question or "history" in normalized_question or "incident" in normalized_question:
        if timeline_events:
            matched_events = _find_relevant_timeline_events(normalized_question, timeline_events)
            if matched_events:
                body = "; ".join(
                    f"{event['date_label']}: {event['title']} ({event['event_type']})"
                    for event in matched_events[:4]
                )
            else:
                body = "; ".join(
                    f"{event['date_label']}: {event['title']}"
                    for event in timeline_events[:4]
                )
        else:
            body = "No timeline captured yet."
        return {
            "answer": f"Timeline context: {body}.",
            "source_summary": interview_sources,
            "model": "rule",
            "answer_style": "timeline-summary",
        }

    if "how" in normalized_question and ("hand off" in normalized_question or "handoff" in normalized_question or "transition" in normalized_question):
        actions = profile.get("recommended_actions", [])
        return {
            "answer": "For a smoother handover: " + "; ".join(actions or ["run one follow-up runbook capture"]),
            "source_summary": interview_sources,
            "model": "rule",
            "answer_style": "handover-guidance",
        }

    if matched_entities:
        if note_hits:
            note_context = [note for note in note_hits if any(
                entity.lower() in (note["content"] + " " + note["title"]).lower() for entity in matched_entities
            )]
            note_excerpt = "; ".join(_sentence_preview(note["content"], 18) for note in note_context[:2])
        else:
            note_excerpt = ""
        return {
            "answer": f"Relevant nodes: {', '.join(matched_entities)}. {summary} {note_excerpt}".strip(),
            "source_summary": interview_sources,
            "model": "rule",
            "answer_style": "entity-summary",
        }

    if answer_bank:
        return {
            "answer": f"Based on the captured interview: {_sentence_preview(answer_bank, 48)}",
            "source_summary": interview_sources,
            "model": "rule",
            "answer_style": "coverage-fallback",
        }

    if note_hits:
        top_note = note_hits[0]
        return {
            "answer": f"No interview field matched this question yet. A relevant repository note says: {_sentence_preview(top_note['content'], 40)}",
            "source_summary": note_sources,
            "model": "rule",
            "answer_style": "repository-fallback",
        }

    return {
        "answer": "No interview knowledge has been captured yet.",
        "source_summary": [],
        "model": "rule",
        "answer_style": "empty-interview",
    }


def _summarize(
    role: str,
    answers: dict[str, str],
    entities: list[GeneratedEntity],
    risk: dict[str, Any],
) -> str:
    named_entities = [entity.name for entity in entities if entity.entity_type != "Role"]
    system_entities = [entity.name for entity in entities if entity.entity_type == "System"][:4]
    process_entities = [entity.name for entity in entities if entity.entity_type == "Process"][:4]
    dependency_entities = [entity.name for entity in entities if entity.entity_type in {"Person or Team", "Knowledge Source"}][:4]
    entity_names = ", ".join(named_entities[:6]) or "the role context"
    strongest_answer = max(answers.values(), key=len, default="No interview answer was provided.")
    compressed = _sentence_preview(strongest_answer, 28).rstrip(".")
    return (
        f"{role} knowledge centers on {entity_names}. "
        f"Core systems are: {_sentence_or_none(system_entities)}. "
        f"Operational patterns include {_sentence_or_none(process_entities)}. "
        f"Key dependency coverage comes from {_sentence_or_none(dependency_entities)}. "
        f"Continuity signal: {compressed}. "
        f"Current knowledge risk is {risk['level']} at {risk['score']}/100."
    )


def _extract_entities(role: str, answer_text: str) -> list[GeneratedEntity]:
    candidates: dict[tuple[str, str], float] = {}
    lower_text = answer_text.lower()

    for entity_type, keywords in ENTITY_KEYWORDS.items():
        for keyword in keywords:
            if re.search(rf"\\b{re.escape(keyword)}\\b", lower_text):
                name = _title_entity(keyword)
                candidates[(name, entity_type)] = max(candidates.get((name, entity_type), 0.0), 0.86)

    for phrase in re.findall(r"\b[A-Z][A-Za-z0-9&/.-]*(?:\s+[A-Za-z0-9][A-Za-z0-9&/.-]*){0,4}\b", answer_text):
        if len(phrase) < 3 or phrase.lower() in {"the", "and", "where", "which", "that", "with"}:
            continue
        candidate_type = _guess_entity_type(phrase)
        candidates[(phrase.strip(), candidate_type)] = max(
            candidates.get((phrase.strip(), candidate_type), 0.0), 0.72
        )
    for noun in _tokenize_answer_phrases(answer_text):
        candidate_type = _guess_entity_type(noun)
        candidates[(noun, candidate_type)] = max(candidates.get((noun, candidate_type), 0.0), 0.64)

    candidates[(role, "Role")] = 0.99
    sorted_candidates = sorted(candidates.items(), key=lambda item: (-item[1], item[0][0]))[:18]
    return [
        GeneratedEntity(
            id=_stable_id("entity", name, entity_type),
            name=name,
            entity_type=entity_type,
            confidence=round(confidence, 2),
        )
        for (name, entity_type), confidence in sorted_candidates
    ]


def _build_relationships(
    role: str,
    entities: list[GeneratedEntity],
    answer_text: str,
) -> list[GeneratedRelationship]:
    role_entity = next((entity for entity in entities if entity.entity_type == "Role"), None)
    if role_entity is None:
        return []

    relationships: list[GeneratedRelationship] = []
    node_index = {entity.id: entity for entity in entities}
    for entity in entities:
        if entity.id == role_entity.id:
            continue
        relationship_type = {
            "System": "OWNS",
            "Process": "RUNS",
            "Risk": "EXPOSED_TO",
            "Knowledge Source": "DOCUMENTED_IN",
            "Person or Team": "DEPENDS_ON",
        }.get(entity.entity_type, "RELATED_TO")
        evidence = _sentence_preview(answer_text, 18)
        relationships.append(
            GeneratedRelationship(
                id=_stable_id("relationship", role_entity.id, entity.id, relationship_type),
                source_id=role_entity.id,
                target_id=entity.id,
                relationship_type=relationship_type,
                evidence=evidence,
                confidence=round(
                    _relationship_confidence(
                        relationship_type,
                        answer_text,
                        source_confidence=node_index[role_entity.id].confidence,
                        target_confidence=entity.confidence,
                    ),
                    2,
                ),
            )
        )

    ordered_entities = [entity for entity in entities if entity.entity_type != "Role"]
    for i in range(0, min(len(ordered_entities), 10), 2):
        source = ordered_entities[i]
        for target in ordered_entities[i + 1 : i + 2]:
            if source.id == target.id:
                continue
            if _entity_sequence_link_exists(source, target, relationships):
                continue
            relationships.append(
                GeneratedRelationship(
                    id=_stable_id("relationship", source.id, target.id, "CONNECTED_WITH"),
                    source_id=source.id,
                    target_id=target.id,
                    relationship_type="CONNECTED_WITH",
                    evidence=_sentence_preview(
                        _first_sentence_containing(answer_text, source.name, target.name),
                        20,
                    ),
                    confidence=round(
                        _relationship_confidence(
                            "CONNECTED_WITH",
                            answer_text,
                            source_confidence=source.confidence,
                            target_confidence=target.confidence,
                        ),
                        2,
                    ),
                )
            )

    risk_entities = [entity for entity in entities if entity.entity_type == "Risk"]
    system_entities = [entity for entity in entities if entity.entity_type == "System"]
    for risk in risk_entities[:3]:
        for system in system_entities[:3]:
            relationships.append(
                GeneratedRelationship(
                    id=_stable_id("relationship", risk.id, system.id, "THREATENS"),
                    source_id=risk.id,
                    target_id=system.id,
                    relationship_type="THREATENS",
                    evidence=f"{risk.name} appears in the same knowledge profile as {system.name}.",
                    confidence=round(
                        _relationship_confidence(
                            "THREATENS",
                            answer_text,
                            source_confidence=risk.confidence,
                            target_confidence=system.confidence,
                        ),
                        2,
                    ),
                )
            )

    return relationships[:28]


def _relationship_confidence(
    relationship_type: str,
    answer_text: str,
    source_confidence: float,
    target_confidence: float,
) -> float:
    base_confidence = {
        "OWNS": 0.88,
        "RUNS": 0.83,
        "EXPOSED_TO": 0.72,
        "DOCUMENTED_IN": 0.77,
        "DEPENDS_ON": 0.79,
        "RELATED_TO": 0.65,
        "CONNECTED_WITH": 0.6,
        "THREATENS": 0.74,
    }.get(relationship_type, 0.63)
    answer_length = len(answer_text.split())
    evidence_boost = min(0.12, answer_length / 2500)
    return max(0.30, min(0.99, base_confidence * 0.58 + source_confidence * 0.28 + target_confidence * 0.14 + evidence_boost))


def _build_timeline(
    role: str,
    answers: dict[str, str],
    answer_text: str,
) -> list[GeneratedTimelineEvent]:
    snippets = list(answers.values())
    sentence_map = [sentence for sentence in re.split(r"(?<=[.!?])\s+", answer_text) if sentence.strip()]
    events = [
        ("Knowledge Capture", "Interview", "Now", f"{role} knowledge interview completed."),
        ("Operational Ownership", "Role Context", "Current", _sentence_preview(sentence_map[0] if sentence_map else answer_text, 22)),
        ("Continuity Risk Signal", "Risk", "Current", _sentence_preview(sentence_map[2] if len(sentence_map) > 2 else answer_text, 22)),
        ("Documentation Map", "Repository", "Next", _sentence_preview(sentence_map[3] if len(sentence_map) > 3 else answer_text, 22)),
        (
            "Successor Handoff",
            "Action",
            "Next",
            _sentence_preview(
                snippets[-1] if snippets else answer_text, 24,
            ) if snippets else "Capture a handoff runbook while context is still fresh.",
        ),
    ]
    return [
        GeneratedTimelineEvent(
            id=_stable_id("timeline", role, title, str(index)),
            title=title,
            event_type=event_type,
            date_label=date_label,
            description=description,
            sequence_number=index,
        )
        for index, (title, event_type, date_label, description) in enumerate(events, start=1)
    ]


def _score_risk(
    role: str,
    answers: dict[str, str],
    entities: list[GeneratedEntity],
) -> dict[str, Any]:
    answer_text = " ".join(answers.values()).lower()
    total_chars = sum(len(answer) for answer in answers.values())
    total_tokens = max(len(re.findall(r"[a-z0-9']+", answer_text)), 1)
    system_count = sum(1 for entity in entities if entity.entity_type == "System")
    process_count = sum(1 for entity in entities if entity.entity_type == "Process")
    person_count = sum(1 for entity in entities if entity.entity_type == "Person or Team")
    source_count = sum(1 for entity in entities if entity.entity_type == "Knowledge Source")
    risk_entity_count = sum(1 for entity in entities if entity.entity_type == "Risk")
    role_count = sum(1 for entity in entities if entity.entity_type == "Role")

    factors: list[dict[str, Any]] = []
    score = 22

    def add_factor(label: str, delta: int, note: str) -> None:
        nonlocal score
        score += delta
        factors.append({"factor": label, "impact": delta, "note": note})

    if total_chars < 500:
        add_factor("Interview brevity", 28, "Capture is too shallow across required prompts.")
    elif total_chars < 800:
        add_factor("Limited depth", 16, "More operational detail lowers uncertainty.")
    else:
        score -= 6
        factors.append({"factor": "Interview depth", "impact": -6, "note": "Sufficient context was provided."})

    if total_tokens > 1100:
        add_factor("Strong answer signal", -7, "Detailed explanations improved continuity confidence.")

    if role in {"Cloud Engineer", "SOC Analyst", "Security Engineer", "System Administrator"}:
        add_factor("Critical operations role", 10, f"{role} depends on live context during incidents.")
    if role in {"Manager", "Dietician"}:
        add_factor("Context-heavy domain", 6, "Steady handoff documentation is important.")

    if system_count == 0:
        add_factor("Missing operational systems", 16, "No primary systems were confidently extracted.")
    elif system_count == 1:
        add_factor("Limited system breadth", 6, "Only one system surfaced strongly.")

    if source_count == 0:
        add_factor("No stored knowledge source", 12, "No explicit knowledge repository signal was extracted.")
    elif source_count >= 2:
        add_factor("Knowledge references present", -8, "Runbooks/docs increase continuity reliability.")

    if person_count >= 1 and person_count < 2:
        add_factor("Single fallback person", 8, "Limited handoff coverage for dependencies.")
    elif person_count >= 3:
        add_factor("Cross-team backup", -6, "Multiple dependents were identified.")

    if process_count == 0:
        add_factor("Undefined process map", 8, "No operational process was extracted.")

    if risk_entity_count:
        add_factor(
            "Documented risk statements",
            min(10 + risk_entity_count * 2, 20),
            "Interview explicitly calls out risk and exception contexts.",
        )

    if role_count == 1:
        add_factor("Role ownership captured", -4, "Primary owner role is clearly extracted.")

    avg_confidence = sum(entity.confidence for entity in entities) / max(len(entities), 1)
    if avg_confidence >= 0.9:
        add_factor("Strong extraction confidence", -8, "Core nodes are consistently high-confidence.")
    elif avg_confidence < 0.75:
        add_factor("Noisy extraction signal", 12, "Entity confidence is uneven or uncertain.")

    high_risk_terms = {
        "manual": 8,
        "undocumented": 13,
        "single point": 16,
        "outage": 11,
        "incident": 9,
        "unknown": 10,
        "approval": 7,
        "compliance": 8,
        "production": 7,
        "critical": 9,
        "rotation": 6,
        "downtime": 8,
    }
    for term, points in sorted(high_risk_terms.items(), key=lambda item: item[0]):
        if term in answer_text:
            add_factor(f"Risk phrase: {term}", points, f"{term.title()} appears in the interview context.")

    # Confidence-weighted penalty damping for high-confidence extraction and strong coverage signals.
    if score < 20:
        score = 20
    if score > 100:
        score = 100
    score = int(round(max(0, min(100, score))))

    sorted_factors = sorted(factors, key=lambda item: (item["impact"], item["factor"]), reverse=True)
    drivers = [f"{item['factor']} ({item['note']})" for item in sorted_factors if item["impact"] > 0][:8]
    if not drivers:
        drivers = ["No major risk escalators detected from this profile."]

    level = "Low" if score < 38 else "Medium" if score < 68 else "High"
    return {
        "score": score,
        "level": level,
        "drivers": drivers[:7],
        "breakdown": sorted_factors[:8],
        "tokens": total_tokens,
        "coverage_chars": total_chars,
    }


def _recommend_actions(
    level: str,
    entities: list[GeneratedEntity],
    breakdown: list[dict[str, Any]],
) -> list[str]:
    actions = ["Capture one follow-up interview with a backup owner."]
    if any(item["factor"] in {"Missing operational systems", "Limited system breadth"} for item in breakdown):
        actions.append("Map the two most critical systems with ownership and rollback notes.")
    if level in {"Medium", "High"}:
        actions.append("Create a one-page successor runbook for the top operational dependency.")
    if level == "High":
        actions.append("Schedule a live handoff review and record the decision history.")
    if any(entity.entity_type == "Knowledge Source" for entity in entities):
        actions.append("Link existing docs to the extracted knowledge profile.")
    if any(item["factor"] == "No stored knowledge source" for item in breakdown):
        actions.append("Attach one handoff or audit note before handover.")
    return actions[:4]


def _coverage_label(answers: dict[str, str]) -> str:
    total_chars = sum(len(answer) for answer in answers.values())
    if total_chars >= 900:
        return "Strong"
    if total_chars >= 450:
        return "Useful"
    return "Starter"


def _guess_entity_type(phrase: str) -> str:
    lowered = phrase.lower()
    if any(word in lowered for word in {"team", "ops", "security", "platform"}):
        return "Person or Team"
    if any(word in lowered for word in {"aws", "azure", "gcp", "kubernetes", "service", "api"}):
        return "System"
    return "Knowledge Source" if any(word in lowered for word in {"docs", "wiki", "runbook"}) else "System"


def _title_entity(keyword: str) -> str:
    known = {
        "aws": "AWS",
        "azure": "Azure",
        "gcp": "GCP",
        "eks": "EKS",
        "iam": "IAM",
        "siem": "SIEM",
        "ci/cd": "CI/CD",
        "oncall": "On-call",
        "on-call": "On-call",
    }
    return known.get(keyword, keyword.replace("-", " ").title())


def _sentence_preview(text: str, max_words: int) -> str:
    words = re.findall(r"\S+", text)
    if not words:
        return "No detail captured yet."
    preview = " ".join(words[:max_words])
    return preview if len(words) <= max_words else preview.rstrip(".,") + "..."


def _tokenize_answer_phrases(text: str, min_len: int = 3) -> list[str]:
    phrases = re.findall(r"\b(?:[a-z0-9][a-z0-9&/._-]*\s+){1,3}[A-Za-z0-9][A-Za-z0-9&/._-]*\b", text.lower())
    cleaned: list[str] = []
    for phrase in phrases:
        normalized = phrase.strip()
        if len(normalized.replace(" ", "")) < min_len:
            continue
        words = [word for word in normalized.split() if word and word not in _STOP_WORDS]
        if len(words) < 2:
            continue
        cleaned.append(normalized.title())
    return list(dict.fromkeys(cleaned))


def _infer_entity_mentions(entities: list[dict[str, Any]], normalized_question: str, limit: int = 5) -> list[str]:
    mentions: list[str] = []
    for entity in entities:
        name = entity["name"].lower()
        if name in normalized_question or any(token in name for token in _tokenize(normalized_question)):
            mentions.append(entity["name"])
        if len(mentions) >= limit:
            break
    return mentions


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2]


def _repository_note_source(note: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "note",
        "id": note.get("id", ""),
        "title": note["title"],
        "source": note.get("source", ""),
        "role": note.get("role", ""),
        "created_at": note.get("created_at", ""),
        "excerpt": _sentence_preview(note["content"], 42),
        "content": note["content"],
    }


def _note_belongs_to_interview_context(note: dict[str, Any], interview: dict[str, Any]) -> bool:
    note_interview_id = note.get("interview_id")
    if note_interview_id and note_interview_id == interview.get("id"):
        return True
    note_role = str(note.get("role") or "").strip().lower()
    interview_role = str(interview.get("role") or "").strip().lower()
    return bool(note_role and interview_role and note_role == interview_role)


def _repository_grounded_sources(
    note_sources: list[dict[str, Any]],
    interview_source: dict[str, Any],
    include_interview_source: bool,
) -> list[dict[str, Any]]:
    if not include_interview_source:
        return note_sources
    return [*note_sources, interview_source]


def _rank_repository_notes(
    normalized_question: str,
    notes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not notes:
        return []
    query_tokens = [token for token in _tokenize(normalized_question) if token not in _STOP_WORDS]
    scored: list[tuple[int, dict[str, Any]]] = []
    for note in notes:
        haystack = " ".join(
            [
                str(note.get("title", "")),
                str(note.get("source", "")),
                str(note.get("content", "")),
            ]
        ).lower()
        score = 0
        for token in query_tokens:
            if token in haystack:
                score += 2
        if note.get("role"):
            score += 1
        if score > 0:
            scored.append((score, note))
    scored.sort(key=lambda item: (-item[0], item[1].get("created_at", ""), item[1].get("title", "")))
    return [note for _score, note in scored]


def _repository_incident_answer(note: dict[str, Any], timeline_events: list[dict[str, Any]]) -> str:
    content = str(note.get("content", "")).strip()
    normalized_content = content.lower()
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", content) if sentence.strip()]
    focus_terms = {
        "false positive",
        "confirmed",
        "no attacker",
        "no attacker activity",
        "credential misuse",
        "expected test automation",
        "rollback simulation",
        "service account",
        "siem rule",
        "five hours",
        "cloudfront",
        "cache",
        "invalidation",
        "expired aws role",
        "failed build",
        "github actions",
    }
    focused = [
        sentence
        for sentence in sentences
        if any(term in sentence.lower() for term in focus_terms)
    ][:4]
    if not focused:
        focused = sentences[:3]

    if "false positive" in normalized_content or "no attacker" in normalized_content:
        lead = (
            "The incident was treated as a false positive because the repository note shows the suspicious "
            "pattern came from approved or expected activity, not attacker activity. "
        )
    elif "cloudfront" in normalized_content or "cache" in normalized_content:
        lead = (
            "Customers saw outdated dashboard assets because the repository note points to stale CloudFront "
            "cache behavior rather than a failed build. "
        )
    else:
        lead = "The repository note points to this explanation: "

    return (lead + " ".join(focused)).strip()


def _repository_risk_answer(note: dict[str, Any], risk_level: str | None, risk_score: int | None) -> str:
    content = str(note.get("content", "")).lower()
    risks = []
    if "five" in content and "hour" in content:
        risks.append("the investigation path was slow enough to create a repeat-response risk")
    if "ci/cd" in content or "pipeline" in content or "deployment" in content:
        risks.append("CI/CD alert ownership and expected automation behavior need clearer documentation")
    if "service account" in content or "privilege" in content or "permission" in content:
        risks.append("service-account and permission-change context is easy to misread during an incident")
    if "siem" in content or "rule" in content or "alert" in content:
        risks.append("SIEM rule tuning and false-positive criteria are not yet captured as a reusable playbook")
    if "developer" in content or "application" in content or "code" in content:
        risks.append("application-code context still depends on the developer who knew the change history")
    if not risks:
        risks.append(_sentence_preview(str(note.get("content", "")), 28))

    risk_context = ""
    if risk_level is not None and risk_score is not None:
        risk_context = f" Current profile risk remains {risk_level} at {risk_score}/100."
    return "Highest continuity risks from this evidence: " + "; ".join(risks[:4]) + "." + risk_context


def _repository_dependency_answer(
    note: dict[str, Any],
    profile: dict[str, Any],
    entities: list[dict[str, Any]],
) -> str:
    content = str(note.get("content", "")).lower()
    dependencies = []
    dependency_terms = {
        "SOC Analyst": ("soc analyst", "soc"),
        "Security Engineer": ("security engineer", "siem", "alert"),
        "Software Developer": ("developer", "application", "code"),
        "CI/CD or Release Owner": ("ci/cd", "pipeline", "deployment", "release"),
        "IAM or Platform Owner": ("iam", "service account", "permission", "privilege"),
    }
    for label, terms in dependency_terms.items():
        if any(term in content for term in terms):
            dependencies.append(label)
    for dependency in profile.get("critical_dependencies", [])[:3]:
        if dependency not in dependencies:
            dependencies.append(dependency)
    if not dependencies:
        dependencies = _infer_entity_mentions(entities, content, limit=5)
    if not dependencies:
        dependencies = ["not yet clear from the captured evidence"]
    return (
        "Key dependencies from this evidence are: "
        + ", ".join(dependencies[:6])
        + ". Open the source note below to inspect the exact meeting or handover context behind that answer."
    )


def _find_relevant_timeline_events(
    normalized_question: str,
    timeline_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matched = []
    for event in timeline_events:
        line = f"{event.get('title', '')} {event.get('event_type', '')} {event.get('description', '')}".lower()
        if any(token in line for token in _tokenize(normalized_question)):
            matched.append(event)
    if not matched:
        return []
    return matched


def _first_sentence_containing(text: str, first_entity: str, second_entity: str) -> str:
    if not text:
        return "No explicit linkage sentence was captured."
    sentences = re.split(r"(?<=[.!?])\s+", text)
    first = first_entity.lower()
    second = second_entity.lower()
    for sentence in sentences:
        lowered = sentence.lower()
        if first in lowered and second in lowered:
            return sentence.strip()
    return sentences[0].strip() if sentences else "No linkage sentence found."


def _entity_sequence_link_exists(
    source: GeneratedEntity,
    target: GeneratedEntity,
    relationships: list[GeneratedRelationship],
) -> bool:
    return any(
        (relationship.source_id == source.id and relationship.target_id == target.id)
        or (relationship.source_id == target.id and relationship.target_id == source.id)
        for relationship in relationships
    )


def _sentence_or_none(items: list[str]) -> str:
    return ", ".join(items) if items else "not explicitly named"


def _answer_with_ollama(
    *,
    question: str,
    role: str,
    summary: str,
    profile: dict[str, Any],
    timeline_events: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    repository_notes: list[dict[str, Any]],
) -> str | None:
    if not OLLAMA_ENABLED:
        return None
    try:
        prompt = _build_ollama_prompt(
            question=question,
            role=role,
            summary=summary,
            profile=profile,
            timeline_events=timeline_events,
            entities=[entity["name"] for entity in entities],
            repository_notes=repository_notes,
        )
        payload = json.dumps(
            {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
            },
        ).encode("utf-8")
        request_obj = _url_request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _url_request.urlopen(request_obj, timeout=OLLAMA_TIMEOUT) as response:
            if getattr(response, "status", 200) >= 400:
                return None
            data = json.loads(response.read().decode("utf-8"))
        answer = str(data.get("response", "")).strip()
        return answer or None
    except Exception as exc:
        if isinstance(exc, _url_error.URLError):
            return None
        if isinstance(exc, TimeoutError):
            return None
        return None


def _build_ollama_prompt(
    *,
    question: str,
    role: str,
    summary: str,
    profile: dict[str, Any],
    timeline_events: list[dict[str, Any]],
    entities: list[str],
    repository_notes: list[dict[str, Any]],
) -> str:
    note_lines = [
        f"- {note.get('title', 'note')}: {_sentence_preview(note.get('content', ''), 20)}"
        for note in repository_notes[:3]
    ]
    event_lines = [
        f"- {event.get('date_label', '')} {event.get('title', '')}: {event.get('description', '')}"
        for event in timeline_events[:5]
    ]
    return (
        "You are the LegacyOS AI search assistant for operational continuity."
        " Answer only from the evidence below. Be concise and cite note evidence when relevant.\n\n"
        f"Role: {role}\n"
        f"Summary: {summary}\n"
        f"Entities: {', '.join(entities[:14])}\n"
        f"Risk: {profile.get('risk_level', 'Unknown')} ({profile.get('risk_score', 'N/A')}/100)\n"
        f"Top actions: {', '.join(profile.get('recommended_actions', []))}\n\n"
        "Timeline:\n"
        f"{'\\n'.join(event_lines) or '- no timeline yet'}\n\n"
        "Repository Notes:\n"
        f"{'\\n'.join(note_lines) or '- no notes attached'}\n\n"
        f"Question: {question}\n"
        "Response format: one short paragraph with any note title in brackets if used."
    )


def _stable_id(*parts: str) -> str:
    return sha256(":".join(parts).encode("utf-8")).hexdigest()[:16]

# Product Backlog — AdéquIA

Owner: Product Owner (PO). Methodology and labels per `docs/10-scrum-github-workflow.md` — 1-week sprints, Fibonacci-ish points (`1 2 3 5 8`), epics mapped to `docs/06-roadmap.md`.

## Vision

AdéquIA automates the matching, scoring, and anomaly detection between individual expert CVs and TDR (tender) requirements, producing a ranked, explainable decision-support report that plugs directly into the bid/no-bid step of the company's tender pipeline — replacing a manual, error-prone CV search with a rubric-based, citation-backed ranking an HR reviewer can approve or override in minutes.

## Personas

**HR Reviewer (primary)** — uploads/maintains the CV database, uploads TDRs, reviews the ranked shortlist per position, approves/rejects/overrides matches. Has zero prior context on "compatibility score" or "anomaly" — the dashboard has to explain itself.

**Bid Manager / Technical Lead (secondary)** — uses the ranked shortlist to make the bid/no-bid call and size the proposal team. Cares about speed and about being able to defend the shortlist to a client or internal stakeholder — the rationale and citations matter more to this persona than the raw score.

## Sprint summary

| Sprint | Dates | Goal | Points | Demoable increment (Sprint Review) |
|---|---|---|---|---|
| 1 | 2026-07-06 → 07-10 | Ingest a real CV/TDR and see it turned into structured data end-to-end | 43 | Upload a real CV/TDR, see the extracted structured fields on screen |
| 2 | 2026-07-13 → 07-17 | Produce a real ranked shortlist with sub-scores for a TDR position | 42 | Matching results page — ranked candidates, real compatibility scores |
| 3 | 2026-07-20 → 07-24 | Every match gets a cited report; a reviewer can approve/reject/override it | 50 | Report view page — rationale, citations, working approve/reject/override |
| 4 | 2026-07-27 → 07-31 | Full dashboard polish, eval rigor, defense-ready deliverables | 35 | Complete styled dashboard + metrics page with real numbers |

Point totals aren't forced equal: Sprint 1 front-loads the riskiest technical integration (multi-key LLM routing) alongside setup work; Sprints 2-3 carry the core pipeline complexity; Sprint 4 cools down into polish. `epic: dashboard-ux` is deliberately spread across every sprint instead of batched into Sprint 4, so each Sprint Review has a real screen to show, not just a status update.

## Backlog

| ID | Epic | Story | Priority | Points | Sprint | Labels |
|---|---|---|---|---|---|---|
| ADQ-1 | devops | Provision Alembic migrations for the full Postgres schema | P0 | 3 | 1 | `type: task` `component: devops` |
| ADQ-2 | devops | Multi-provider model routing: Groq + Gemini key-pool rotation with local Ollama fallback | P0 | 8 | 1 | `type: story` `component: backend` `component: ai-pipeline` |
| ADQ-3 | ingestion-extraction | Parse CV/TDR documents (text-PDF, docx) into raw text | P0 | 5 | 1 | `type: story` `component: ai-pipeline` |
| ADQ-4 | ingestion-extraction | Spike: sample real CVs/TDRs, confirm OCR need | P1 | 2 | 1 | `type: spike` `component: ai-pipeline` `component: data` |
| ADQ-5 | ingestion-extraction | Structured extraction for CV via Pydantic schema | P0 | 8 | 1 | `type: story` `component: ai-pipeline` |
| ADQ-6 | ingestion-extraction | Structured extraction for TDR + section localization | P0 | 8 | 1 | `type: story` `component: ai-pipeline` |
| ADQ-7 | dashboard-ux | Bare-bones upload + extraction-preview page | P0 | 5 | 1 | `type: story` `component: frontend` |
| ADQ-8 | ingestion-extraction | Annotate gold extraction set (kickoff, ongoing) | P1 | 3 | 1 | `type: task` `component: data` |
| ADQ-9 | company-profile | Request historical staffing decisions + TDR variety from company | P0 | 1 | 1 | `type: task` `component: data` `needs-company-input` |
| ADQ-10 | matching-engine | Build skill/certification taxonomy seed | P0 | 5 | 2 | `type: story` `component: data` `component: ai-pipeline` |
| ADQ-11 | matching-engine | Coarse retrieval / shortlisting pre-filter (no LLM calls) | P0 | 5 | 2 | `type: story` `component: ai-pipeline` |
| ADQ-12 | matching-engine | `normalize_skills`: embedding retrieval (pgvector) | P0 | 8 | 2 | `type: story` `component: ai-pipeline` |
| ADQ-13 | matching-engine | `normalize_skills`: reranker pass | P1 | 3 | 2 | `type: story` `component: ai-pipeline` |
| ADQ-14 | matching-engine | `normalize_skills`: agentic retry (query rewrite on low confidence) | P1 | 5 | 2 | `type: story` `component: ai-pipeline` |
| ADQ-15 | matching-engine | `score` node: hard filters | P0 | 3 | 2 | `type: story` `component: ai-pipeline` |
| ADQ-16 | matching-engine | `score` node: weighted embedding similarity sub-scores | P0 | 5 | 2 | `type: story` `component: ai-pipeline` |
| ADQ-17 | dashboard-ux | Matching results page (ranked list, scores, sub-score bars) | P0 | 5 | 2 | `type: story` `component: frontend` |
| ADQ-18 | devops | First retrieval metrics (Precision@K / Recall@K) vs. gold matching set | P1 | 3 | 2 | `type: task` `component: ai-pipeline` |
| ADQ-19 | matching-engine | `score` node: LLM judgment for qualitative criteria + memory calibration vs. `historical_decisions` | P0 | 8 | 3 | `type: story` `component: ai-pipeline` |
| ADQ-20 | anomaly-detection | `detect_anomalies` node: rule-based checks + LLM plausibility pass | P0 | 8 | 3 | `type: story` `component: ai-pipeline` |
| ADQ-21 | anomaly-detection | Synthetic anomaly injection framework (6 types) + precision/recall/F1 run | P0 | 8 | 3 | `type: story` `component: ai-pipeline` `component: data` |
| ADQ-22 | reporting-explainability | `generate_report` node: rationale + citations | P0 | 8 | 3 | `type: story` `component: ai-pipeline` |
| ADQ-23 | reporting-explainability | Injection-resistance guardrail test set | P0 | 5 | 3 | `type: story` `component: ai-pipeline` `component: data` |
| ADQ-24 | matching-engine | HITL interrupt node + `historical_decisions` write-back on override | P0 | 5 | 3 | `type: story` `component: backend` `component: ai-pipeline` |
| ADQ-25 | dashboard-ux | Report view page (rationale, citations, approve/reject/override) | P0 | 8 | 3 | `type: story` `component: frontend` |
| ADQ-26 | dashboard-ux | Upgrade Sprints 1-3 pages to the styled shadcn/ui dashboard (candidates + TDR pages, empty states, tooltips) | P0 | 5 | 4 | `type: story` `component: frontend` |
| ADQ-27 | dashboard-ux | Metrics dashboard page | P1 | 5 | 4 | `type: story` `component: frontend` |
| ADQ-28 | dashboard-ux | First-run guided tour | P1 | 3 | 4 | `type: story` `component: frontend` |
| ADQ-29 | reporting-explainability | Wire RAGAS faithfulness/groundedness eval | P1 | 5 | 4 | `type: task` `component: ai-pipeline` |
| ADQ-30 | reporting-explainability | Start DeepEval CI regression suite | P1 | 5 | 4 | `type: task` `component: devops` `component: ai-pipeline` |
| ADQ-31 | devops | LangSmith/Langfuse tracing end-to-end, screenshot-ready | P2 | 2 | 4 | `type: task` `component: devops` |
| ADQ-32 | reporting-explainability | Lightweight local PII pre-processing before any cloud LLM call | P2 | 5 | 4 | `type: story` `component: ai-pipeline` |
| ADQ-33 | devops | Final metrics pass + documented methodology | P0 | 3 | 4 | `type: task` `component: docs` |
| ADQ-34 | devops | Defense rehearsal prep (trace screenshot, metrics table, demo script) | P1 | 2 | 4 | `type: task` `component: docs` |

34 stories, 170 points across 4 sprints.

## Icebox / Stretch (explicitly unscheduled)

Per `docs/00-overview.md`: build only after the core system above is done and stable. Not assigned to any of the 4 sprints.

| Epic | Item | Notes |
|---|---|---|
| company-profile | Company capability data model + ingestion (past project references, aggregate headcount/specialties, firm certifications) | Smaller, mostly-static dataset — different shape from the CV/TDR core, do not let it expand into a second full subsystem |
| company-profile | Company profile view (dashboard stretch page) | Feeds bid/no-bid from the firm side rather than the individual side |
| reporting-explainability | Auto-formatted CV annex generation for the winning proposal | Step 5 of the bid pipeline — out of core scope |
| reporting-explainability | Full local/on-device PII pre-processing before *any* cloud LLM call | Sprint 4 (ADQ-32) ships a lightweight masking version; this is the fuller on-device version, deferred |

## Explicitly out of scope (this internship)

Tender discovery/sourcing, bid submission logistics, fine-tuning/training any model, self-hosted inference infrastructure, full GraphRAG/knowledge graph — see `docs/00-overview.md`.

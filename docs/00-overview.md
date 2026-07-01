# 00 — Overview

**Project name: AdéquIA** — see `07-branding.md` for the full naming/branding rationale.

## What this project is

An AI system that automates the matching, scoring, and anomaly detection between
**individual expert CVs** (employees of the company) and **TDR** (Termes de Référence
— mission/tender requirement documents), producing a ranked, explainable
decision-support report.

This is not a generic "resume screener." It is built for a specific business process:
**consulting/tender bidding**, where a TDR specifies one or more required expert
positions (e.g. "Team Leader," "Technical Expert," "QA Lead"), each with its own
mandatory diploma, minimum years of experience, certifications, languages, and
sector experience. The company must find, for each required position, the best
internal candidate — fast, consistently, and with a defensible rationale.

## The business problem (as stated by the company)

The company bids on tenders through a pipeline that looks like this:

1. **Discover tender** — sales/BD monitors procurement portals
2. **Analyze the TDR/RFP** — extract scope, required profiles, deadlines, evaluation criteria
3. **Bid / no-bid decision** — do we have the expertise and available staff?
4. **Estimate cost & effort** — team size, timeline, budget
5. **Prepare proposal & pricing** — technical solution, staffing plan, CVs annex
6. **Submit bid**

Today, step 3 is manual: someone reads the TDR, then tries to recall or search
which internal experts might qualify. This is slow, and — critically — **error-prone
in a way that costs money**: a missed good match means passing on a winnable bid; a
missed disqualifying gap means committing to staff who don't actually meet the
requirements.

## Where this system sits

This system **is** the automation of step 3, and its output directly feeds steps 4
and 5:

- **Input**: a parsed TDR (one or more required expert positions) + the internal
  CV/expert database
- **Output**: for each required position, a ranked list of candidates with a
  compatibility score, a breakdown by criterion, flagged anomalies/gaps, and a
  citation-backed rationale
- **Downstream use**: the ranking informs the bid/no-bid call (step 3), the shortlist
  drives team sizing (step 4), and the winning candidates' matched CVs + the
  system's rationale become part of the staffing section of the proposal (step 5)

Steps 1 and 6 are out of scope — that's sourcing and submission logistics, not
matching intelligence.

## Scope

**Core (must-have):**
- Individual expert CV ↔ TDR expert-position matching, scoring, anomaly detection,
  and report generation, for French-primary documents (English CVs/TDRs also
  supported; no Arabic)
- Full HR-facing dashboard (Next.js) for reviewing rankings, overriding decisions,
  and viewing reports
- Evaluation harness with real, measurable metrics (see `04-evaluation-metrics.md`)

**Stretch (nice-to-have, only after core is solid):**
- Lightweight **company-level capability check** — a much smaller, mostly-static
  dataset (past project references, aggregate headcount/specialties, firm-held
  certifications) that can feed the same bid/no-bid decision from the *company*
  side rather than the *individual* side. Different data shape, much smaller
  surface — do not let this expand into a second full subsystem. Build it only if
  the core system is done and stable.
- Auto-formatted CV annex generation for the winning proposal (step 5)
- Local/on-device PII pre-processing before data reaches any cloud LLM API

**Explicitly out of scope for this internship:**
- Tender discovery/sourcing (step 1)
- Bid submission logistics (step 6)
- Fine-tuning or training any model
- Self-hosted inference infrastructure (vLLM, Kubernetes, etc.) — you're calling
  APIs, not serving models
- Full GraphRAG / knowledge graph — a flat skill taxonomy with embedding similarity
  is the right complexity for this timeline

## Success criteria

The project succeeds if, at the end of one month, you can show:

1. A working end-to-end pipeline: upload a real TDR + query the real CV database →
   get a ranked, scored, anomaly-flagged, cited report for each expert position
2. A dashboard an HR reviewer could actually use, including override capability
3. A metrics report with real numbers (not just "it works"): extraction accuracy,
   retrieval quality, scoring agreement with human reviewers (ideally against real
   historical staffing decisions), anomaly detection precision/recall, time saved,
   cost per CV
4. A clear, defensible explanation of every architectural choice — why LangGraph,
   why hybrid scoring instead of pure LLM judgment, why pgvector instead of a
   separate vector DB, why RAG instead of keyword matching — each grounded in a
   real constraint, not "because it's trendy"

## Glossary — jargon to project role

| Term | Role in this project |
|---|---|
| LangGraph | Orchestrates the multi-agent pipeline as a stateful, auditable graph |
| RAG / dense retrieval | Matches CV skills to TDR requirements despite different wording (FR/EN synonyms) |
| Agentic RAG / query rewriting | Retries a low-confidence skill match with a reformulated query before falling back to an LLM judgment call |
| Reranker | Re-sorts top retrieved skill/cert matches by relevance before they're trusted |
| Hybrid scoring | Rule-based hard filters (diploma present? years met?) + weighted embedding similarity + LLM judgment for qualitative criteria |
| Anomaly/gap detection agent | Checks the extracted CV for internal inconsistencies (date overlaps, expired certs, implausible claims) |
| HITL (human-in-the-loop) | The dashboard pause point where an HR reviewer approves or overrides a ranking |
| Semantic/episodic memory | Past staffing decisions stored and retrieved to calibrate new scores |
| MCP | Exposes the skill taxonomy and historical-decisions store as tools the agents call |
| Guardrails / prompt injection defense | CV text is always treated as data to extract from, never as an instruction to the LLM |
| Model routing | Cheap/fast model for extraction, stronger model for final scoring judgment and report writing |
| RAGAS / DeepEval | The evaluation harness measuring faithfulness, retrieval quality, and catching regressions |
| Citation generation | Every score and anomaly in the report links back to the exact source CV/TDR passage |

## Reading order for Claude Code

1. `00-overview.md` (this file) — context and scope
2. `01-architecture.md` — system design and tech stack, with justifications
3. `02-data-schemas.md` — Pydantic models and Postgres schema
4. `03-agent-pipeline.md` — the LangGraph graph, node by node
5. `04-evaluation-metrics.md` — what to measure, how, and target values
6. `05-frontend-dashboard.md` — the Next.js dashboard spec
7. `06-roadmap.md` — the 4-week build plan
8. `07-branding.md` — name, slogan, palette, typography, tone
9. `08-company-data-checklist.md` — what to request from the company, and when
10. `09-devops-cicd.md` — Docker, GitHub Actions, hosting
11. `10-scrum-github-workflow.md` — sprint cadence, epics, labels, board setup

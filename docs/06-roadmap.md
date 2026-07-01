# 06 — Roadmap (4 weeks)

General principle: **build the eval harness alongside the feature it measures,
not after.** Every week below pairs a pipeline capability with the metric that
validates it.

## Week 1 — Ingestion, extraction, foundations

- FastAPI skeleton, Postgres schema from `02-data-schemas.md`, pgvector extension
- Document parsing (`ingest` node): text-PDF and docx first; check real samples
  early for scanned/image CVs and add OCR fallback only if actually needed
- `extract` node: structured extraction for both CV and TDR into the Pydantic
  schemas, with `source_span` on every field
- Start annotating the gold extraction set in parallel (don't wait until the
  extractor is "done" — annotate as you go so you catch schema gaps early)
- **Ask the company for real historical staffing decisions** if not already
  provided — this unlocks your best scoring-agreement metric later
- Milestone: given a real CV and TDR, produce correct structured JSON for both

## Week 2 — Matching intelligence

- Build the skill/certification taxonomy (start small, curated, expand as real
  data reveals gaps)
- `normalize_skills` node: embedding retrieval + reranking + agentic retry
- `score` node: hard filters, weighted similarity, LLM judgment step, memory
  calibration against `historical_decisions`
- Wire the LangGraph state machine and conditional edges (hard-filter
  short-circuit)
- Compute first retrieval metrics (Precision@K, Recall@K) against the gold
  matching set as soon as normalize_skills exists — don't wait for scoring
- Milestone: given a TDR position and a set of CVs, produce a ranked list with
  sub-scores

## Week 3 — Anomaly detection, reporting, eval rigor

- `detect_anomalies` node: rule-based checks + LLM plausibility pass
- Build the synthetic anomaly injection framework and run it against the
  detector — get real precision/recall numbers
- `generate_report` node: rationale + citations
- Guardrails: injection-resistance test set, verify zero-effect on score
- Wire RAGAS for faithfulness/groundedness, start the DeepEval regression suite
- HITL interrupt + `historical_decisions` write-back on override
- Milestone: full pipeline runs end-to-end with a real report and a first full
  metrics pass

## Week 4 — Dashboard, polish, defense prep

- Next.js dashboard: all pages from `05-frontend-dashboard.md`, in priority
  order (matching results and report view first, metrics dashboard second,
  company-profile stretch last if time allows)
- LangSmith/Langfuse tracing wired and screenshot-ready
- Metrics dashboard finalized with real numbers, documented methodology
- Write-up: architecture decisions with justifications (pull straight from
  `01-architecture.md`), the metrics table, and the business-process mapping
  (pull from your own understanding of the bid pipeline)
- Rehearse the defense: the trace screenshot, the metrics table, and a live
  demo on real (anonymized) data are your three strongest assets

## Ongoing, every week

- Keep the gold datasets growing as you encounter real edge cases
- Re-run the DeepEval suite after any pipeline change, not just at the end
- Log cost/latency from day one — retrofitting cost tracking at the end loses
  the early data points that make the "cost per CV" number credible

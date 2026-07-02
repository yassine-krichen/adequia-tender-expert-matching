# Sprint 2 Plan

**Dates:** 2026-07-13 → 2026-07-17 (5 working days)
**Capacity:** 42 points committed.

**Sprint Goal:** Given a TDR position and the CV pool, produce a real ranked shortlist with sub-scores — visible in a working matching results view.

**Definition of Ready / Done:** see `definition-of-ready-and-done.md`.

## Sprint backlog

| ID | Story | Priority | Points | Acceptance summary |
|---|---|---|---|---|
| ADQ-10 | Build skill/certification taxonomy seed | P0 | 5 | Curated starter taxonomy (canonical terms + aliases) seeded into `skill_taxonomy` with embeddings; expandable as real data reveals gaps |
| ADQ-11 | Coarse retrieval / shortlisting pre-filter | P0 | 5 | Embedding similarity + rough years/sector check shortlists ~8-10 candidates per position, zero LLM calls |
| ADQ-12 | `normalize_skills`: embedding retrieval | P0 | 8 | Each raw skill/requirement term embedded and matched against `skill_taxonomy` via pgvector |
| ADQ-13 | `normalize_skills`: reranker pass | P1 | 3 | Top-K retrieved candidates reranked before the best match is accepted; reranking-lift metric computed |
| ADQ-14 | `normalize_skills`: agentic retry | P1 | 5 | Low-confidence match triggers one query rewrite (expand abbreviation / translate FR↔EN) and retries once |
| ADQ-15 | `score` node: hard filters | P0 | 3 | Mandatory diploma / min. years / mandatory certs checked; failure sets `hard_filter_passed=false` and short-circuits to report |
| ADQ-16 | `score` node: weighted embedding similarity sub-scores | P0 | 5 | Per-criterion sub-scores (skills, sector) computed from normalized skills, combined into a weighted `compatibility_score` |
| ADQ-17 | Matching results page | P0 | 5 | Ranked candidate list, compatibility score, hard-filter status, sub-score bars — **Sprint 2 demoable slice** |
| ADQ-18 | First retrieval metrics vs. gold matching set | P1 | 3 | Precision@K / Recall@K computed and recorded against the gold matching set as soon as `normalize_skills` exists |

Note: the `score` node's LLM-judgment step and memory calibration are deferred to Sprint 3, grouped with the other qualitative-reasoning and reporting work (ADQ-19).

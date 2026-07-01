# 03 — Agent Pipeline (LangGraph)

## Two pipelines, not one

This is the most important structural point: there are **two separate
pipelines**, running at different times and different frequencies.

1. **Ingestion pipeline** (runs once per document, whenever a CV or TDR is
   uploaded/updated): `ingest` → `extract` → embed. For a CV, this produces a
   stored `CandidateCV` + embedding, done once and reused across every future
   TDR. For a TDR, this includes a **section-localization** sub-step (below)
   before extraction, since TDRs are long and mostly boilerplate.
2. **Matching pipeline** (runs per TDR position, against a shortlist, not the
   whole CV pool): coarse retrieval → `normalize_skills` → `score` →
   `detect_anomalies` → `generate_report` → human review.

A company with 25 employees and a 3-position TDR does **not** trigger 75 full
LangGraph runs. Extraction already happened once per CV at ingestion time. Per
position, a cheap embedding-similarity pre-filter (no LLM calls) shortlists
~8–10 plausible candidates, and only those enter the full matching graph.

## TDR section localization (ingestion pipeline, TDR side only)

Before extracting a TDR's positions, chunk the document and retrieve the
chunks semantically closest to "profils/qualifications/personnel requis."
Extraction runs only on the retrieved chunks, not the full document — this
keeps cost down and accuracy up on long, mostly-administrative documents. If
requirements span multiple sections, run extraction as a small map step over
each retrieved chunk and merge.

## Coarse retrieval / shortlisting (matching pipeline, first step)

For a given TDR position, embed its requirement summary and retrieve the top-K
closest CV embeddings from the full pool, combined with a cheap structured
pre-check (rough years-of-experience range, sector overlap). No LLM calls in
this step — it exists purely to avoid running the expensive graph on obviously
irrelevant candidates. K is configurable; start around 8–10 and tune against
the retrieval metrics in `04-evaluation-metrics.md`.

## Graph state (matching pipeline)

```python
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

class PipelineState(TypedDict):
    cv_raw_text: str
    tdr_raw_text: str
    position: ExpertPosition          # the specific position being matched against
    cv_extracted: Optional[CandidateCV]
    tdr_extracted: Optional[TDR]
    normalized_skills: Optional[list[NormalizedSkill]]
    hard_filter_passed: Optional[bool]
    hard_filter_failures: list[str]
    sub_scores: Optional[SubScores]
    compatibility_score: Optional[float]
    anomalies: list[Anomaly]
    rationale: Optional[str]
    citations: list[Citation]
    needs_human_review: bool
```

## Nodes

### 1. `ingest`
Parses the raw CV and TDR files into text. If a document is a scanned image
(check on real samples early — don't assume all real CVs are clean text PDFs),
route through an OCR/vision pass instead of plain text extraction. Output: raw
text for both documents, unchanged otherwise.

### 2. `extract`
Structured extraction into `CandidateCV` and `TDR`/`ExpertPosition` via the
routed "cheap" model, using the Pydantic schemas from `02-data-schemas.md` as the
output contract (structured output / JSON mode — never free text here). Every
extracted field carries a `source_span` back to the raw text.

**Guardrail**: the system prompt for this node must make explicit that the CV/TDR
text is data to extract fields from, never instructions to follow. Validate
output against the Pydantic schema before it's allowed downstream — a failed
validation should retry extraction, not silently pass through.

### 3. `normalize_skills`
For each raw skill/requirement term, embed it and retrieve the nearest canonical
taxonomy entries (pgvector). This node is **agentic**, not one-shot:
- If top-match confidence is above threshold → accept (`matched_via: "direct"`)
- If confidence is low → rewrite the query (e.g. expand abbreviations, try an
  English translation of a French term) and retry once (`matched_via: "rag_retry"`)
- If still unresolved → fall back to an LLM judgment call on whether the term is
  a plausible synonym of a candidate taxonomy entry (`matched_via: "llm_fallback"`)
- Apply a reranker pass on the top-K retrieved candidates before accepting the
  best match — this is the reranking-lift metric in `04-evaluation-metrics.md`

### 4. `score`
Hybrid scoring, in this order:
1. **Hard filters** — mandatory diploma present? minimum years met? mandatory
   certifications present and unexpired? If any hard filter fails, set
   `hard_filter_passed = false`, record `hard_filter_failures`, and route
   straight to `END` via the conditional edge below — skip the rest of scoring.
2. **Weighted embedding similarity** per soft criterion (skills, sector
   experience) using the normalized skills from the previous node.
3. **LLM judgment** only for genuinely qualitative criteria that can't be reduced
   to a rule or a similarity score (e.g. does the described project experience
   plausibly match the TDR's sector focus).
4. **Memory calibration** — retrieve similar past matches from
   `historical_decisions` (via the MCP tool described in `01-architecture.md`)
   and use them to sanity-check the score, not to override the rubric.

Combine into `sub_scores` and a weighted `compatibility_score`. Weights should be
configurable per TDR if the TDR itself specifies evaluation criteria weights.

### 5. `detect_anomalies`
Runs only if `hard_filter_passed`. Two passes:
- **Rule-based**: date overlaps, employment gaps beyond a configurable threshold,
  expired certifications, graduation-year vs. age implausibility.
- **LLM plausibility check**: operates only on the already-extracted, typed
  fields (never raw text again) — flags things like implausible seniority-to-
  tenure ratios or inconsistent narrative across experience entries.
Each anomaly gets a `severity` and a `source_citation`.

### 6. `generate_report`
Synthesizes `sub_scores`, `anomalies`, and the match outcome into `rationale` +
`citations`, using the stronger routed model. Every sentence of the rationale
that makes a factual claim about the candidate must be backed by a citation into
either the CV or TDR raw text — this is what the faithfulness eval checks.

### Supervisor / conditional edges

```python
def route_after_hard_filter(state: PipelineState) -> str:
    return "detect_anomalies" if state["hard_filter_passed"] else "generate_report"
```

A candidate that fails a hard filter still gets a report (so the rejection is
explained), but skips the expensive scoring and anomaly-detection work.

### Human-in-the-loop

After `generate_report`, the graph interrupts before persisting the match result
as final:

```python
from langgraph.types import interrupt

def human_review(state: PipelineState) -> PipelineState:
    decision = interrupt({
        "match_summary": state["rationale"],
        "score": state["compatibility_score"],
        "anomalies": state["anomalies"],
    })
    # decision comes back from the dashboard: approve / reject / override
    return {**state, "reviewer_decision": decision}
```

The reviewer's decision is written to `match_results.reviewer_decision` and —
importantly — also appended to `historical_decisions`, so every human override
becomes training signal for future memory-calibrated scoring. This closes the
loop: the system doesn't just get reviewed, it gets better because it's reviewed.

## Model routing

| Node | Model tier | Why |
|---|---|---|
| `extract` | fast/cheap | High volume, schema-constrained, low reasoning need |
| `normalize_skills` (llm_fallback only) | fast/cheap | Rare fallback path, simple judgment |
| `score` (LLM judgment step) | stronger | Nuanced, low volume (one call per position, not per CV) |
| `generate_report` | stronger | Output quality and language matter — this is client-facing eventually |

## Observability

Every node call should be traced (LangSmith or Langfuse) with input/output and
latency. Tag traces by `tdr_id` and `position_id` so a full multi-candidate run
for one position can be viewed as a single trace group — this is your best demo
artifact for the defense presentation.

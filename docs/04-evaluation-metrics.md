# 04 — Evaluation & Metrics

This file is what turns the project from "we built a pipeline" into "we measured
it and it works." Build the eval harness in week 1, alongside the extraction
node — do not leave this for the end.

## Datasets you need

1. **Gold extraction set**: 50–100 real (anonymized) CVs and TDRs, manually
   annotated with correct structured fields. Small but high-value — this is what
   validates the `extract` node.
2. **Gold matching set**: labeled CV–position pairs with a human-assigned
   match/no-match or ranking, ideally sourced from **real historical staffing
   decisions** if the company can share them (ask early — see below).
3. **Synthetic anomaly set**: take clean CVs from the gold set and programmatically
   inject known anomaly types (see below) to get labeled positive/negative
   anomaly examples — this is the only practical way to get a real
   precision/recall number, since genuine labeled anomalies are rare in practice.
4. **Injection-resistance set**: CVs with known prompt-injection strings embedded
   in various fields, expected to have zero effect on the final score.

**Ask the company on day one**: can they share which candidates were actually
proposed/selected for past TDRs? A dataset of real historical bid/staffing
decisions is the single highest-value dataset for this project — it's what lets
you report genuine agreement between the AI and expert human judgment, instead of
only synthetic validation.

## Metrics

### Extraction quality
- **Field-level F1** against the gold extraction set (per field type: education,
  certifications, experience, dates)
- Target: >90% F1 on structured fields for clean text-PDF CVs

### Retrieval / matching quality
- **Precision@K, Recall@K, NDCG** on the gold matching set (skill/requirement
  pairs labeled as true matches vs. not)
- **Reranking lift**: same metrics computed with and without the reranker pass,
  reported as a delta — this isolates the value of that specific component
- **Agentic-retry lift**: match accuracy with vs. without the query-rewrite retry
  step in `normalize_skills`

### Scoring agreement
- **Spearman correlation / Cohen's kappa** between the AI's compatibility ranking
  and human reviewer ranking on the gold matching set (or, ideally, real
  historical decisions)
- This is the number that matters most for demonstrating the tool is trustworthy
  enough to influence a real bid/no-bid call

### Anomaly detection
- **Precision, recall, F1** on the synthetic anomaly set, per anomaly type
- **False positive rate on clean CVs** — equally important; an over-triggering
  system is as useless as a silent one

### Report quality
- **Faithfulness / groundedness** (RAGAS-style): sample generated rationales,
  check every factual claim traces to a real citation in the source text
- **Citation coverage**: % of claims in the rationale that carry a valid citation

### Guardrails
- **Injection-resistance pass rate**: % of the injection-resistance set where the
  final score/rationale is unaffected by the injected string

### Efficiency
- **Time per CV–position match**, end-to-end, vs. an estimated manual review
  baseline (get this baseline from HR directly, or time yourself doing a small
  sample manually as a proxy)
- **Cost per CV** (token cost), and **cost per 100 CVs processed**, broken down by
  node (extraction vs. scoring vs. report) — this is what validates the model
  routing decision in `03-agent-pipeline.md`
- **Latency p50/p95** for a single CV–position match

## Synthetic anomaly injection — design

For each clean CV in the gold set, generate variants with exactly one injected
anomaly, so ground truth is known precisely:

| Anomaly type | Injection method |
|---|---|
| `employment_gap` | Remove a middle experience entry, leave the surrounding dates as-is |
| `date_overlap` | Shift one experience entry's dates to overlap another |
| `expired_certification` | Change a certification's expiry date to the past, leave it listed as current |
| `education_date_inconsistency` | Set graduation year implausibly close to or before birth-implied age |
| `unverifiable_claim` | Insert a vague, unfalsifiable achievement claim with no supporting detail |
| `title_seniority_mismatch` | Inflate a job title relative to the years of experience and responsibilities listed |

Run the pipeline on both the clean and injected versions; the detector should
flag the injected version and not the clean one.

## Wiring into CI (DeepEval)

Set up a small DeepEval suite that runs the gold sets above against the current
pipeline on every meaningful change, and fails the build if key metrics regress
past a threshold (e.g. extraction F1 drops more than 3 points, faithfulness drops
below 0.85). This is what turns "we tested it once" into a real regression gate —
worth building even at small scale, since the story of *having* a CI eval gate is
itself a strong engineering point for the report.

## Reporting format

For the final internship deliverable, present these as a single metrics
dashboard (see `05-frontend-dashboard.md`) plus a one-page summary table —
this is your bullet-point source material, keep the numbers precise and the
methodology (what dataset, what sample size) documented next to each one.

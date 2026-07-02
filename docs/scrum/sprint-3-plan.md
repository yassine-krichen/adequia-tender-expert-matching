# Sprint 3 Plan

**Dates:** 2026-07-20 → 2026-07-24 (5 working days)
**Capacity:** 50 points committed — the heaviest sprint by design, since core feature completion (scoring judgment, anomalies, reporting, HITL) concentrates here.

**Sprint Goal:** Every match gets a full cited report with anomaly flags, and a reviewer can approve/reject/override it — in a working report view. This is the sprint where the human-in-the-loop actually closes.

**Definition of Ready / Done:** see `definition-of-ready-and-done.md`.

## Sprint backlog

| ID | Story | Priority | Points | Acceptance summary |
|---|---|---|---|---|
| ADQ-19 | `score` node: LLM judgment + memory calibration | P0 | 8 | Qualitative criteria (e.g. sector-focus match) judged by the stronger model tier; result sanity-checked against similar `historical_decisions`, not overridden by them |
| ADQ-20 | `detect_anomalies` node: rule-based + LLM plausibility | P0 | 8 | Date overlaps, employment gaps, expired certs, grad-year implausibility (rule-based); implausible seniority/tenure or inconsistent narrative (LLM pass on typed fields only) |
| ADQ-21 | Synthetic anomaly injection framework | P0 | 8 | All 6 anomaly types from `docs/04-evaluation-metrics.md` injected into gold-set CVs; detector run against clean + injected pairs; precision/recall/F1 per type recorded |
| ADQ-22 | `generate_report` node: rationale + citations | P0 | 8 | Sub-scores + anomalies + outcome synthesized into a plain-language rationale; every factual claim carries a citation into CV or TDR raw text |
| ADQ-23 | Injection-resistance guardrail test set | P0 | 5 | CVs with known prompt-injection strings; final score/rationale verified unaffected — 100% pass rate on the test set |
| ADQ-24 | HITL interrupt + `historical_decisions` write-back | P0 | 5 | Graph interrupts before persisting a final match result; reviewer decision written to `match_results.reviewer_decision` and appended to `historical_decisions` |
| ADQ-25 | Report view page | P0 | 8 | Full rationale with clickable citation highlights, anomaly flags by severity, approve/reject/override controls with a required note on override — **Sprint 3 demoable slice** |

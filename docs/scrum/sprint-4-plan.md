# Sprint 4 Plan

**Dates:** 2026-07-27 → 2026-07-31 (5 working days)
**Capacity:** 35 points committed — intentional wind-down after Sprint 3's peak, room for polish and defense prep.

**Sprint Goal:** Full dashboard polish, remaining pages, eval rigor, and defense-ready deliverables.

**Definition of Ready / Done:** see `definition-of-ready-and-done.md`.

## Sprint backlog

| ID | Story | Priority | Points | Acceptance summary |
|---|---|---|---|---|
| ADQ-26 | Upgrade Sprints 1-3 pages to the styled dashboard | P0 | 5 | Candidate CV management + TDR upload/breakdown pages rebuilt with shadcn/ui, empty states that explain rather than show blank, tooltips on non-obvious concepts |
| ADQ-27 | Metrics dashboard page | P1 | 5 | Extraction F1, retrieval precision/recall, scoring agreement, anomaly detection precision/recall, time saved, cost per CV — pulled from the eval harness output, screenshot-able |
| ADQ-28 | First-run guided tour | P1 | 3 | Skippable walkthrough: upload TDR → see positions → see ranked matches → understand score → understand anomaly → approve/override |
| ADQ-29 | Wire RAGAS faithfulness/groundedness eval | P1 | 5 | RAGAS run against generated rationales; faithfulness/groundedness/context-precision recorded |
| ADQ-30 | Start DeepEval CI regression suite | P1 | 5 | Gold sets wired into `eval.yml` (already scaffolded); build fails if extraction F1 drops >3pts or faithfulness drops below 0.85 |
| ADQ-31 | LangSmith/Langfuse tracing end-to-end | P2 | 2 | Every node call traced with input/output/latency, tagged by `tdr_id`/`position_id`; one full multi-candidate run viewable as a single trace group |
| ADQ-32 | Lightweight local PII pre-processing | P2 | 5 | Name/phone/email/photo masked locally before any cloud LLM call; toggleable, documented as a partial mitigation (full on-device version stays in the icebox) |
| ADQ-33 | Final metrics pass + documented methodology | P0 | 3 | All `docs/04-evaluation-metrics.md` metrics computed with real numbers; dataset and sample size documented next to each one |
| ADQ-34 | Defense rehearsal prep | P1 | 2 | Trace screenshot, metrics table, and a live demo script on real (anonymized) data assembled as the three defense assets |

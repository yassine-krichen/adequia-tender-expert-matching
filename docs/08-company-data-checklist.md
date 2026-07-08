# 08 — Company Data & Info Request Checklist

Bring this list to the company early — several items unlock or materially
change the architecture, so the earlier you ask, the less rework later.

## Data

- [ ] **All current employee CVs** (bulk export to start the database)
- [ ] **Historical staffing decisions** — which candidates were actually
      proposed/selected for past TDRs. This is the single highest-value item:
      it's what turns the scoring-agreement metric from synthetic to real.
- [ ] **A range of past TDR documents** — different sectors, different
      clients/donors, different document formats/templates — not just one clean
      example. Extraction robustness depends on seeing the real variance.
- [ ] **Any existing internal evaluation rubric** — do they already have a way
      of weighting education vs. experience vs. certifications when judging a
      candidate? Don't reinvent this if it exists; encode it.
- [ ] **Any existing skill/competency taxonomy** they use internally, if one exists.

## Process & ownership

- [ ] **Who owns/maintains the CV repository today** — HR system, shared
      drive, ATS, informal folder? Determines whether the dashboard's CV
      upload feature replaces or supplements an existing process.
- [ ] **Who the intended dashboard users are** — HR only, or also bid
      managers/technical leads? Affects whether role-based access is needed.
- [ ] **Roughly how many employees total**, and **how many TDRs are processed
      per month** — determines whether cost/latency targets are a real
      constraint or secondary.

## Policy — ask before building, not after

- [ ] **Data confidentiality policy**: is anonymized CV data allowed to be sent
      to a third-party LLM API (Claude, or similar), or must processing stay
      fully on-prem / local models only? This changes the architecture
      materially — confirm before any real CV touches a cloud API.
- [ ] **Are TDRs typically clean text PDFs, or sometimes scanned/image documents?**
      Determines whether an OCR fallback in ingestion is actually needed.
- [ ] **Confirm document languages**: French primary, English sometimes, no
      Arabic — already assumed in the spec, but worth a direct confirmation
      once you're in the building talking to the actual team.

## Nice-to-have, if the conversation allows

- [ ] Access to someone in HR/bid management for periodic feedback during the
      internship (a 15-minute check-in weekly is enough) — this is what lets
      you tune the hard-filter thresholds and scoring weights against real
      judgment instead of guessing, and gives you a natural source of override
      data for the human-in-the-loop step.

## Working assumptions (no company response received)

This list was handed over at project start; no answers came back by the end
of Sprint 1. Development can't stay blocked on it, so the assumptions below
are the best-effort, most-defensible guesses given what's actually observable
(the 3 real TDR samples provided, the shape of the roles they describe, and
standard practice for a firm bidding on this kind of contract) — **not
confirmed facts**. Each should be revisited the moment a real answer arrives;
several (especially confidentiality policy) could change the architecture.

- **All current employee CVs**: not provided. Development proceeds on 11
  synthetic CVs (`docs/cvs/synthetic/`) as fixtures, each persona designed
  to cover a real skill/domain gap exposed by the real TDR sample set
  below (AI/RAG, mobile + conversational AI, cybersecurity, .NET
  enterprise, software architecture, on top of the original 6 classic
  IT-staffing profiles). Assumption: real CV volume is small enough (see
  headcount guess below) that a manual bulk upload through the
  dashboard's own upload flow is a workable one-time migration — no
  bespoke bulk-import tooling built speculatively.
- **Historical staffing decisions**: not provided, and likely doesn't exist
  in structured form — assume it's tribal knowledge / informal notes at
  best. Rather than leaving the matching eval blocked on that, the team
  built and actively grows its own ground-truth gold matching set
  (`backend/tests/eval/fixtures/matching/gold_matching_set.json`, 11
  entries as of Sprint 2 — one per candidate in the pool, most
  hand-crafted with the same rigor a real labeling pass would need, one
  pulled verbatim from a genuinely real TDR extraction rather than
  invented). This *is* the working ground truth this project scores
  retrieval quality against, not a stopgap. What real historical
  decisions would still add on top: actual acceptance/rejection
  *outcomes* (was the top-ranked candidate actually the one staffed, and
  if not, why) — a different, higher-value signal than "is this
  candidate a plausible fit," which is what the current gold set checks.
- **Range of past TDR documents**: 13 real documents have been sourced and
  used as fixtures (up from an initial 3) — spanning AI/RAG knowledge
  hubs, AI chatbot prototypes, secure web development training, .NET/C#
  enterprise systems, mobile + conversational-AI apps, and more, across
  several donors/clients (AfDB, ILO, World Bank GovTech, UNFPA-adjacent,
  and others) — not just one program's house style. The chunk-retrieval
  and extraction-prompt work (hybrid keyword+embedding scoring,
  requirement-based position filtering, atomic-term skill extraction, and
  a cross-chunk merge fix — see docs/12-sprint-2-handoff.md and the
  Sprint 2 report chapter) was driven directly by what this now-larger,
  more varied sample set demanded.
- **Internal evaluation rubric**: none provided — assume none is formalized
  in writing. Scoring weights (education vs. experience vs. certifications)
  are implemented as configurable values, not hardcoded, specifically so
  they can be corrected once someone with real hiring/bid judgment reviews
  them — don't mistake the current defaults for a validated rubric.
- **Existing skill/competency taxonomy**: none provided — assume none
  exists. `SkillTaxonomy` is designed to grow organically from skills
  actually seen in extracted CVs/TDRs rather than seeded from an external
  list.
- **Who owns the CV repository today**: unknown — assume informal (shared
  drive / email attachments), consistent with no ATS having been mentioned.
  The dashboard's own upload flow is assumed to become the system of record
  going forward, not a sync target for some other system.
- **Intended dashboard users**: unknown — assume both HR and
  bid/technical leads need access, since assembling a bid team is a
  technical judgment call as much as an HR one (see the real TDR staffing
  sections: diploma + years + prior similar-project experience, which a
  technical lead is best placed to judge). MVP ships without granular
  role-based access (single shared login) to avoid building permissions
  logic against a guess — add real RBAC once actual user roles are
  confirmed, not before.
- **Headcount / TDRs per month**: unknown — assumed small (an internship-
  scoped project for a firm of roughly a few dozen technical/functional
  staff, single-digit to low-double-digit TDRs per month), based on the
  scale of the example bid team compositions seen (1 chef de projet + 1
  architecte + 3 consultants + 6 développeurs per mission). This is why
  cost/latency stayed secondary to correctness this sprint — free-tier
  multi-provider LLM routing (ADQ-2) assumes call volume stays modest.
- **Data confidentiality policy**: no answer — defaulted to the most
  conservative assumption, since CVs are personal data. The architecture
  already supports a fully local fallback (Ollama) for every LLM call in
  the pipeline; if the company says cloud APIs (Groq/Gemini) aren't
  allowed, disabling those two in `ModelRouter` and running Ollama-only
  is a config change, not a redesign. Treat that as still open until
  confirmed — don't assume cloud LLM usage is approved for real candidate
  data.
- **Scanned vs. clean-text TDRs**: all 13 real samples (the original 3 plus
  10 sourced this sprint) are clean, extractable text (PDF/DOCX, no OCR
  needed) — assume this is representative and OCR (ADQ spike work) stays
  a fallback path, not the primary one, until a real scanned document
  actually shows up.
- **Document languages**: the sample set is now mixed French/English (the
  original 3 were all French; several of the 10 added this sprint —
  World Bank/AfDB/ILO-sourced — are English) — the spec's original
  "French primary" assumption no longer fully holds. Extraction/matching
  is embedding-based, not keyword-matched, so it degrades gracefully
  across languages, but this is worth a direct confirmation with the
  company rather than continuing to assume French-only.
- **Periodic HR/bid-management feedback access**: not arranged — evaluation
  and threshold tuning rely solely on the self-built synthetic gold set
  (ADQ-8) until/unless this becomes available. This is the single biggest
  risk to the scoring/matching feature actually being useful in practice —
  surface it early and often rather than letting a synthetic-only metric
  quietly stand in for real validation.

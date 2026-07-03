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

- **All current employee CVs**: not provided. Development proceeds on 6
  synthetic CVs (`docs/cvs/synthetic/`) as fixtures. Assumption: real CV
  volume is small enough (see headcount guess below) that a manual bulk
  upload through the dashboard's own upload flow is a workable one-time
  migration — no bespoke bulk-import tooling built speculatively.
- **Historical staffing decisions**: not provided, and likely doesn't exist
  in structured form — assume it's tribal knowledge / informal notes at
  best. The scoring-agreement metric (ADQ evaluation work) stays calibrated
  against a hand-built synthetic gold set (ADQ-8) for the foreseeable
  future, not real historical outcomes. Flag this explicitly in any report
  or demo — it's a real gap, not a solved problem.
- **Range of past TDR documents**: 3 real samples were provided and used as
  fixtures. They're internally consistent — French-language, public-sector/
  donor-funded (World Bank GovTech program), long multi-annex documents
  (100–270+ pages) with the actual staffing requirements buried in one small
  section — so the assumption is this pattern is the norm rather than an
  outlier. The chunk-retrieval work this sprint (hybrid keyword+embedding
  scoring, requirement-based position filtering) was driven directly by
  what these 3 documents demanded, on the bet that future TDRs look similar.
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
- **Scanned vs. clean-text TDRs**: all 3 real samples were clean,
  extractable text (PDF/DOCX, no OCR needed) — assume this is representative
  and OCR (ADQ spike work) stays a fallback path, not the primary one, until
  a real scanned document actually shows up.
- **Document languages**: all 3 real TDR samples are French, consistent with
  the spec's original assumption (French primary, no Arabic observed) —
  treat as reasonably confirmed by direct evidence, more so than the other
  items on this list.
- **Periodic HR/bid-management feedback access**: not arranged — evaluation
  and threshold tuning rely solely on the self-built synthetic gold set
  (ADQ-8) until/unless this becomes available. This is the single biggest
  risk to the scoring/matching feature actually being useful in practice —
  surface it early and often rather than letting a synthetic-only metric
  quietly stand in for real validation.

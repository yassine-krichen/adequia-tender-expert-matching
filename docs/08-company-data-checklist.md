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

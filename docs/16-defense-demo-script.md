# 16 — Defense demo script

A literal, numbered walkthrough for the internship defense, using this
project's real fixtures (`docs/tdrs/*.pdf`, `docs/cvs/synthetic/*`) against
the live dev stack (`docker compose up -d`, `http://localhost:3000`). Every
number/anomaly/citation quoted below was observed on a real run against
these exact fixtures (2026-07-21) — expect small variation (LLM judgment
isn't perfectly deterministic run to run), but the shape of what you'll see
should match.

## Read this first: the one risk-mitigation recommendation that matters most

**Pre-seed the TDR and candidate pool before the actual defense.** Live TDR/CV
extraction against the free-tier LLM providers is genuinely slow and
quota-fragile — a real run this session hit Gemini's daily free-tier quota
(20 requests/day) mid-extraction and had to fall back to local Ollama, which
took several minutes per document instead of seconds. That is not a look you
want live, in front of a jury, with a clock running.

Concretely, before defense day:
1. Upload `docs/tdrs/govtech-education-ecosystem.pdf` (or your chosen TDR)
   and every CV in `docs/cvs/synthetic/` into the dev stack ahead of time,
   and run matching once, so the data in steps 2–7 below is already sitting
   in the database.
2. For step 1 (TDR upload) and the CV upload portion of step 2 below, **show
   a screenshot of a prior run instead of live-triggering extraction** during
   the defense. Narrate what the screenshot shows (the progress steps:
   "Parsing → Locating the relevant section → Extracting section N of 12 →
   Combining results") rather than watching a spinner for real.
3. Everything from step 3 onward (matching against already-extracted data,
   score breakdowns, anomalies, citations, the review/override flow, the
   LangSmith trace, the metrics page) is fast and reliable against
   pre-seeded data — **this is the part that should actually be live.**

## Step 1 — Upload a TDR (screenshot, not live — see above)

File: `docs/tdrs/govtech-education-ecosystem.pdf`.

Navigate to `/tdrs`, upload the file. Talking points while showing the
screenshot of a prior run:
- The upload triggers background extraction (`app/worker/tasks.py`), not a
  blocking request — the UI polls `/tdrs/{id}/status` every 1.5s and shows
  live progress (`"Extracting section N of 12…"`).
- Before extraction, the TDR is chunked and only the chunks semantically
  closest to "profils, qualifications et personnel requis" are kept (12 of
  however many total chunks this ~pages-long TDR produces) — this is the
  section-localization step described in `docs/03-agent-pipeline.md`, and it
  exists because real TDRs are mostly administrative boilerplate.
- Once done, the extracted result showed mission title **"Gestion des
  profils scolaires"** and 4 expert positions, including **"chef de projet"**
  (Bac+5, 15 years minimum) and **"architecte technique"** (Ingénieur Bac+5,
  10 years minimum) — both pulled with a verbatim `source_span` back to the
  original TDR text, not paraphrased.

## Step 2 — Show the candidate pool (screenshot for upload, live for the list)

Navigate to `/candidates`. The roster already has the 9 synthetic candidates
from `docs/cvs/synthetic/` (Amine Ferjani, Ines Belhadj, Karim Trabelsi, Mehdi
Aouadi, Nadia Ben Salah, Salma Gharbi, Walid Mejri, Yosra Chaabane, Youssef
Kammoun) if pre-seeded per the recommendation above. Talking points:
- CV extraction runs **once per employee, at ingestion time** — never
  re-run per TDR (`docs/01-architecture.md`'s "two-phase matching" design
  decision).
- **PII pre-processing (ADQ-32)**: mention that before any of this text
  reached a cloud LLM, `app/common/pii.py` masked the candidate's email,
  phone, and own name — the resulting `full_name` field you see in this
  table (e.g. "Karim Trabelsi") is still correct, because it's read back
  from a local name-detection heuristic on the *original* text, not from
  the LLM's masked-prompt output. This ties directly into step 6 below.

## Step 3 — Run matching (live)

On the TDR's page, click "Run matching". Talking points while it runs (fast
against a pre-seeded candidate pool — no LLM calls in the coarse-retrieval
step, only in the shortlist's scoring/anomaly/report steps):
- Coarse retrieval first shortlists ~8-10 plausible candidates per position
  via cheap embedding similarity, before the expensive LangGraph pipeline
  (`normalize_skills → score → detect_anomalies → generate_report → human
  review`) runs on just that shortlist — not the whole candidate pool.
- The UI polls `/tdrs/{id}/match-status` the same way TDR extraction did.

## Step 4 — Ranked matches per position (live)

Once matching finishes, the position table on `/tdrs` shows each shortlisted
candidate with compatibility %, hard-filter pass/fail, and a skill/sector
sub-score breakdown. On a real run:
- For **"chef de projet"** (15 years minimum), every candidate in this
  fixture set failed the hard filter on experience (all topped out around
  12-15 years) — a good moment to explain the hard-filter-first design:
  candidates who don't meet a mandatory requirement are never scored
  further (no wasted LLM calls, and no risk of a soft score
  overriding a hard requirement).
- For **"architecte technique"** (10 years minimum), **Karim Trabelsi**
  passed the hard filter and scored **52% compatibility** (skill_score 0.0,
  sector_score 1.0, qualitative_fit_score 0.9) — a good example of a
  partial match worth walking through in detail (step 5).

## Step 5 — Score breakdown, citation, and rationale (live)

Click through to Karim Trabelsi's match report (`/matches/{match_id}`).
Talking points, quoting the real rationale observed on this run:
- The rationale is generated in **French**, citing concrete evidence:
  *"Ce profil correspond à 52% des critères demandés... il est important de
  noter que le candidat ne possède pas la compétence en architecture
  technique. En revanche, son expérience en encadrement technique d'une
  équipe de développeurs backend/frontend... sont des atouts pour le
  poste."*
- Every claim in that rationale is backed by a `Citation` with a
  `source_span` — either quoted straight from the CV (e.g. *"Architecte
  logiciel — ST2i (Secteur public / IT), 2019-02 – présent..."*) or from the
  LLM's own structured assessment. This is what `docs/04-evaluation-metrics.md`'s
  "report quality" / groundedness metric checks systematically — here you're
  showing one instance of it by hand.

## Step 6 — Anomaly example (live)

Same match report. On this run, Karim Trabelsi triggered a **`title_seniority_mismatch`**
anomaly (severity: `info`):
> *"The candidate's current title 'Architecte logiciel' implies a level of
> seniority that is supported by their experience as 'Développeur backend
> senior' and their responsibilities as 'Encadrement technique d'une équipe
> de 6 développeurs backend/frontend'"*

Talking point: this is an *info*-severity anomaly (not a red flag) — it's
the anomaly detector confirming consistency, which is a good example that
the detector isn't just tuned to always find something wrong. If you want a
higher-severity example for contrast, walk through a candidate who failed
the hard filter instead (e.g. any "chef de projet" candidate above) and
explain the `Insufficient experience: X years (minimum 15.0)` hard-filter
failure message shown as a tooltip on the "Failed" badge.

## Step 7 — Approve / reject / override flow (live)

Still on the match report page:
- Click **Approve** or **Reject** for a straightforward decision — this
  resumes the LangGraph checkpoint (`interrupt()` in `human_review`) that's
  been durably paused since `generate_report` ran, and writes
  `reviewer_decision`/`decided_at` back to `match_results`.
- Click **Override** instead, pick a direction (approve/reject anyway), and
  note the UI requires a **non-empty note** to submit — this is enforced
  server-side too (`ValidationFailedError` in `ReportingService.submit_review`),
  not just a client-side nicety. The override, once submitted, also appends
  a row to `historical_decisions` — closing the loop for future scoring
  calibration (`docs/03-agent-pipeline.md`).

## Step 8 (bonus) — Tie back to the LangSmith trace (live, if time allows)

Open the LangSmith project (or screenshot from a prior run — see
`docs/01-architecture.md`'s tracing note and the trace screenshot captured
for ADQ-31/34). Talking points:
- **One parent trace per matching run** (`matching_run`) groups every
  candidate × position `LangGraph` sub-run underneath it — not a flat list
  of unrelated traces. Confirmed live: a single TDR's matching run against
  4 positions × ~10 shortlisted candidates produced one `matching_run` root
  with 40 child runs, each individually filterable by `tdr:<id>` /
  `position:<id>` tags.
- Drill into one candidate's sub-run to show the node-level breakdown:
  `normalize_skills → score → detect_anomalies → generate_report`, each its
  own child run with its own latency and input/output.
- **Strongest combined talking point**: open an `extract_cv` trace and show
  the actual `ChatOllama`/`ChatGroq` input — the traced prompt reads
  `"[NOM]\n[EMAIL] – [PHONE]\n..."`, never the candidate's real name/email/
  phone, while the resulting `CandidateCV.full_name` in the API response is
  still correct. This is ADQ-31 (tracing) and ADQ-32 (PII masking) proving
  each other's claims in one screen.

## Step 9 — Metrics page (live)

Navigate to `/metrics`. Talking points:
- This is real eval-harness output (`docs/04-evaluation-metrics.md`), not a
  static table hand-typed for the defense — extraction quality, retrieval
  quality, anomaly detection, guardrail resistance, scoring agreement,
  report groundedness, and efficiency (time/cost per candidate–position
  match), each with a plain-language explanation of what it actually
  measures (the `InfoTooltip` next to each group heading).
- If a number looks conspicuously perfect or a group is empty, say so
  plainly rather than glossing over it — this project's whole pitch is
  measured rigor, and a jury will notice evasiveness faster than an honest
  gap.

## After the fact: what still needs a human before defense day

- **Trace screenshot**: grab an actual LangSmith UI screenshot (not just the
  API-confirmed structure this session verified) and drop it in
  `docs/report/assets/screenshots/` — this session could query LangSmith's
  API to confirm run-tree structure, but could not drive a browser to
  screenshot the UI itself.
- **Metrics page screenshot**: same — grab one from `http://localhost:3000/metrics`
  once real data is loaded, for the report/slides.
- **Rehearse this exact script once, live, against the pre-seeded stack**,
  end to end, before the actual defense — a script that's never been run
  for real is still a hypothesis, not a plan.

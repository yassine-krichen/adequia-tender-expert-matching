# 20 — Demo day plan (2026-08-03)

This is both your rehearsal test pass and your actual demo script. Run it
once tonight for real (uses live LLM calls — that's the point, it's your
only rehearsal) and it becomes your rehearsed walkthrough for tomorrow.

---

## 0. Pre-flight (5 min)

1. Confirm Docker Desktop + Ollama are running (`docs/15-sprint-4-handoff.md`
   env gotchas — both are known to not survive a machine restart).
2. `docker compose ps` — all 8 services should show `Up`/`healthy`.
3. Convert `docs/tdrs/demo-mfpma-plateforme-talents.md` to PDF (strip the
   HTML comment block at the top first if your converter renders it — most
   Markdown→PDF tools won't, but check the output). Keep the visible
   *"Note interne — ne pas diffuser..."* paragraph near the end of Section
   IV — that's the live guardrail demo, it must survive into the PDF.
4. Open `http://localhost:3000` and `http://localhost:8000/docs` (Swagger)
   in two tabs — you'll need Swagger live for the taxonomy-approval step.

---

## 1. Quick UI polish pass (10 min) — confirm last session's batch is solid

Go through this fast, it's verification not deep testing:

- [ ] `/` — workspace dashboard: candidate/TDR counts show pool-size copy
      + icons, "Learn more →" link to `/about` works.
- [ ] `/about` — pitch content (hero, how it works, features, metrics
      teaser with mini radial gauges) renders correctly.
- [ ] `/metrics` — all 7 groups show their charts (2 donuts on extraction,
      bars on retrieval/report_quality, radar on anomaly_detection, gauges
      on guardrails/scoring_agreement, area+bar on efficiency). Toggle
      dark mode, confirm colors adapt.
- [ ] `/tdrs` and `/candidates` — Force reprocess checkbox looks like a
      proper shadcn checkbox, not a native one.
- [ ] Past TDRs table — should now show only 7 clean entries (cleaned up
      tonight), no horizontal scroll needed to see Status/Created.
- [ ] Theme toggle button in top nav cycles light/dark/system.
- [ ] Click into a candidate, a TDR, and (after step 3 below) a match
      report — confirm each has a working back link.
- [ ] Notice the subtle fade-in on page load and hover lift on the
      workspace quick-link cards — shouldn't feel flashy.

If anything's off, flag it and we fix before moving to the actual demo
content below.

---

## 2. Upload the demo TDR (5-10 min, real LLM call)

1. Go to `/tdrs`, upload `demo-mfpma-plateforme-talents.pdf`.
2. Watch the status messages (parsing → retrieving → extracting → merging).
3. Once done, confirm all **4 expert positions** extracted:
   - Chef de projet SI
   - Ingénieur QA / Testeur Logiciel
   - Architecte Technique
   - Expert(e) en Intelligence Artificielle / Data Scientist
4. **Check the injected note didn't do anything**: none of the 4 positions
   should show a 100% compatibility score at this stage (matching hasn't
   even run yet) and nothing about the extraction should look hijacked.
   Worth a one-line callout live: *"there's a fake instruction buried in
   this TDR trying to tell the AI to auto-score everyone 100% — the system
   treats it as text to read, not a command to obey."*

If `mission_title` or any position looks malformed, that's a real signal
to look at before tomorrow — tell me and we'll adjust the source TDR text.

---

## 3. Run matching and walk the 4 scenarios (15-20 min, real LLM calls)

Click "Run matching" on the uploaded TDR. This is the core of the demo —
each position was deliberately designed to hit a different code path.

### Position 1 — Chef de projet SI: the clean showcase
**Expect**: Nadia Ben Salah near the top, hard filter passed, skill_score
and sector_score both strong, a real (non-null) qualitative_fit_score, a
citation-grounded French rationale paragraph. **Talking point**: this is
the "everything works end to end" case — hybrid scoring (hard filters +
skill/sector math + one LLM judgment call), then a report where every
sentence cites a real fact.

### Position 2 — Ingénieur QA: anomaly detection + live taxonomy growth
**Expect**: Yosra Chaabane matched, but with an **anomaly flagged** — her
CV has a real ~1-year employment gap (graduated 2019, hired Oct 2020) that
the rule-based anomaly checker should catch. Her `skill_score` should also
reflect a partial gap: "Selenium" is a required skill that was
*deliberately* left out of the taxonomy tonight.

**Live demo move**: switch to the Swagger tab (`localhost:8000/docs`),
call `GET /admin/skill-candidates?status=pending`, find "Selenium" in the
list, then call `POST /admin/skill-candidates/{id}/approve` with a
canonical name. **Talking point**: *"the taxonomy has a backend admin API
for exactly this — an unmatched skill got captured automatically, and a
human approves it before it becomes real, so the taxonomy only grows from
things people actually typed, not silently guessed."* Note live: this
approval affects *future* matching runs, not this specific match result
already computed — that's by design (`docs/18` section 4.1).

### Position 3 — Architecte Technique: the honest rejection
**Expect**: strong architects (Karim Trabelsi, Nizar Chebbi) show up in the
shortlist by skill/sector fit, but **both fail the hard filter** — neither
holds the required ISO 27001 certification. Click into one of their match
reports: it should show a clear, pre-written rejection explanation (no
qualitative_fit_score, no wasted LLM call) rather than a low score.
**Talking point**: *"a highly qualified candidate still gets correctly
rejected because of one specific missing requirement, and the system
explains exactly why instead of guessing or forcing a number."*

### Position 4 — Expert IA / Data Scientist: the modern-stack showcase
**Expect**: Ines Belhadj, very strong match — her CV has 100% taxonomy
coverage on Python/ML/GenAI/RAG/LangChain, so skill_score should be near
1.0, sector fit strong, real qualitative_fit_score. **Talking point**: this
is the most topically relevant position to AdéquIA's own tech stack — good
note to end the walkthrough on.

**If live results don't match these expectations exactly** — that's fine,
say so honestly rather than forcing it (the app's own eval philosophy is
"honest numbers, not fabricated ones"). LLM scoring has real variance.

---

## 4. Metrics page (5 min)

Walk to `/metrics`, point at 2-3 charts, mention the honest caveats: the
scoring_agreement gauge is deliberately smaller/muted with its `n=2` note
right next to it, and the TDR extraction F1 is still the document-level
proxy (92.3%) rather than a field-level number — say so if asked, it's a
credibility point, not a weakness to hide (`docs/17`, `docs/19`).

---

## 5. If you get asked business/scope questions

You don't have real supervisor answers for baseline manual time, historical
staffing examples, deployment intent, or bid/no-bid scope. `docs/19-assumed-supervisor-answers.md`
has reasoned, clearly-labeled *assumptions* for all four, with the
reasoning spelled out — read it before tomorrow so you can speak to it
confidently as "here's my reasoned estimate, not confirmed data."

---

## 6. Timing budget (fits in ~35-45 min)

| Step | Time |
|---|---|
| Pre-flight | 5 min |
| UI polish pass | 10 min |
| Upload demo TDR | 5-10 min |
| Run matching + 4 scenarios | 15-20 min |
| Metrics page | 5 min |

---

## 7. If something breaks live tomorrow

- Rate limit / slow extraction: this happened before under heavy prior
  testing load (`docs/17`'s environment gotchas). If it's slow, narrate
  through it honestly — *"this is falling back to a local model because
  the free API tier is rate-limited, which is itself a feature, not a
  bug"* — that's a real, true, and good story, not an excuse.
- If tonight's rehearsal run already produced good match results, you can
  fall back to walking through **those saved results** live tomorrow
  instead of re-running the LLM calls fresh — the match data persists in
  the DB, no need to re-upload.

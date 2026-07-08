# Spike: OCR need assessment (ADQ-4)

**Question.** Do the CV/TDR documents AdéquIA will ingest need an OCR fallback, or is direct text extraction (`pypdf` / `python-docx`, ADQ-3) sufficient?

**Method.** Ran `extract_raw_text()` (ADQ-3) against every real and synthetic document available so far, and computed extracted-characters-per-page for the PDFs — a page that yields near-zero text despite having visible content is the signature of a scanned/image-only page that direct extraction can't read.

## Sample

| File | Type | Pages | Extracted chars | Chars/page |
|---|---|---|---|---|
| `TDR (8).pdf` | real TDR | 193 | 324,334 | ~1,680 |
| `2. TDR Mise en place du SI CI_Avenant contrat_V2.docx` | real TDR | — | 56,400 | n/a (docx) |
| `DP _ Developpement de Applicatif avec 4 modules-revu TAM-ST2I (5).docx` | real TDR | — | 40,952 | n/a (docx) |
| `nadia-ben-salah.pdf` | synthetic CV | 1 | 1,301 | 1,301 |
| `salma-gharbi.pdf` | synthetic CV | 1 | 1,112 | 1,112 |
| `yosra-chaabane.pdf` | synthetic CV | 1 | 789 | 789 |
| `karim-trabelsi.docx` | synthetic CV | — | 1,083 | n/a (docx) |
| `mehdi-aouadi.docx` | synthetic CV | — | 1,001 | n/a (docx) |
| `amine-ferjani.docx` | synthetic CV | — | 1,010 | n/a (docx) |

A scanned page with no embedded text layer typically yields well under 100 chars/page (usually 0, since `pypdf`/`python-docx` only read embedded text objects, never rasterized image content). Every PDF sample here — including a 193-page real TDR — extracted 700+ chars/page, and every docx extracted several hundred to tens of thousands of characters.

## Finding

**No OCR fallback needed for the current sample set.** All 3 real TDRs and all 6 synthetic CVs are native text documents (text-PDF or docx), not scans. `ingest`'s existing `CorruptDocumentError` on empty-text extraction (ADQ-3) already gives a safety net: if a future document *is* scanned, extraction will raise instead of silently returning empty text, which is enough to flag the case for a manual look rather than requiring OCR infrastructure to be built speculatively now.

## Follow-up

Revisit this if the company's response to the ADQ-9 data request (`docs/08-company-data-checklist.md`) includes scanned CVs or TDRs — at that point, file a proper OCR story (e.g. `pytesseract` or a hosted OCR API) rather than retrofitting one under time pressure.

**Sprint 2 addendum:** 10 more real TDRs and 5 more synthetic CVs were added this sprint (pool now 13 real TDRs, 11 synthetic CVs — see `docs/08-company-data-checklist.md`). Not re-measured with the same char/page rigor as the table above, but all 10 new TDRs were read directly (via full-text extraction, same code path) while mining vocabulary for the skill taxonomy expansion, and every one came back as clean, readable, non-garbled prose — consistent with this spike's finding, not a contradiction of it. Worth a real re-measurement if OCR ever becomes a live question, rather than treating this note as equivalent evidence.

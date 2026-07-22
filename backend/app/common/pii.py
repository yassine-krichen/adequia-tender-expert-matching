import re

# Cross-cutting: used by both the candidates (CV) and tdrs (TDR) features
# before any text is handed to a cloud LLM provider (ADQ-32). Deliberately a
# lightweight regex/heuristic, not an NLP/NER dependency (no presidio/spacy
# in this project) -- a best-effort mitigation, not full PII compliance.

_EMAIL_REGEX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Phone numbers seen in this project's real CV fixtures are written with a
# country code and space-separated groups (e.g. "+216 23 147 963") or, less
# often, without the country code ("23 147 963", French-style "0X XX XX XX
# XX"). Deliberately only "." and whitespace are treated as valid group
# separators -- NOT "-": this project's CVs write date ranges/certification
# months with hyphens ("2019-08 -- present", "(2021-07)"), and treating "-"
# as a phone separator would mask those as phone numbers.
_PHONE_WITH_COUNTRY_CODE_REGEX = re.compile(r"\+\d{1,3}[\s.]?\d{1,3}(?:[\s.]\d{2,8}){1,4}")
# A "+"-prefixed number is a strong, unambiguous phone signal on its own --
# no separator required to trust it, whether written with separators
# (above) or glued together (e.g. "+21620123456"). Trusted unconditionally,
# same as _PHONE_WITH_COUNTRY_CODE_REGEX.
_PHONE_COMPACT_WITH_COUNTRY_CODE_REGEX = re.compile(r"\+\d{8,15}")
# Deliberately NOT applied everywhere: this shape ("XX XXX") is identical to
# how French text writes a plain number with a thousands separator (e.g. a
# TDR budget figure or population count -- found live against a real TDR
# fixture: "16 500 jeunes" was wrongly masked as a phone number). Only
# trusted on a line that also carries an email address or an explicit
# phone label -- exactly how every real CV fixture in this project writes
# a phone number ("prenom.nom@example.com -- +216 XX XXX XXX").
_PHONE_LOCAL_REGEX = re.compile(r"(?<!\d)\d{2}(?:[\s.]\d{2,8}){1,3}(?!\d)")
# Same number, no internal separator at all (e.g. "0555987654"). A bare
# 8-12 digit run is otherwise indistinguishable from any other figure in
# free text (a budget line, a reference number...), so it gets the exact
# same email/label gating as _PHONE_LOCAL_REGEX above -- never trusted on
# its own.
_PHONE_COMPACT_LOCAL_REGEX = re.compile(r"(?<!\d)\d{8,12}(?!\d)")
_PHONE_LABEL_REGEX = re.compile(r"(?i)\b(t[ée]l(?:[ée]phone)?|gsm|mobile|portable)\b")


def mask_contact_info(text: str) -> str:
    """Masks email addresses and phone-like number sequences with
    `[EMAIL]`/`[PHONE]` placeholders. Safe to apply to both CV and TDR text
    -- can't collide with mission_title/client/position extraction, those
    are never digit/@ sequences.
    """
    masked_lines = []
    for line in text.split("\n"):
        masked_line = _EMAIL_REGEX.sub("[EMAIL]", line)
        masked_line = _PHONE_WITH_COUNTRY_CODE_REGEX.sub("[PHONE]", masked_line)
        masked_line = _PHONE_COMPACT_WITH_COUNTRY_CODE_REGEX.sub("[PHONE]", masked_line)
        if "[EMAIL]" in masked_line or _PHONE_LABEL_REGEX.search(masked_line):
            masked_line = _PHONE_LOCAL_REGEX.sub("[PHONE]", masked_line)
            masked_line = _PHONE_COMPACT_LOCAL_REGEX.sub("[PHONE]", masked_line)
        masked_lines.append(masked_line)
    return "\n".join(masked_lines)


_NAME_LABEL_REGEX = re.compile(
    r"(?im)^\s*(?:nom(?:\s+(?:et|&)\s+pr[ée]nom)?|pr[ée]nom(?:\s+(?:et|&)\s+nom)?)\s*[:\-]\s*(.+?)\s*$"
)
_CAPITALIZED_WORD = r"[A-ZÀ-Þ][a-zà-ÿ'’.-]*"
_NAME_LINE_REGEX = re.compile(rf"^\s*({_CAPITALIZED_WORD}(?:\s+{_CAPITALIZED_WORD}){{1,3}})\s*$")
# A capitalized 2-4 word line is ALSO how this project's real CVs write a
# job-title headline above the name (e.g. "Chef De Projet Senior" --
# reproduced live, this wrongly won as "the name" and leaked the real name
# unmasked). Excludes any such line from being treated as a name, whether
# found via the proximity signal or the fallback scan below.
_JOB_TITLE_WORD_REGEX = re.compile(
    r"(?i)\b("
    r"chef|cheffe|senior|junior|expert|experte|consultant|consultante|"
    r"ing[ée]nieur[e]?|directeur|directrice|manager|architecte|"
    r"d[ée]veloppeur|d[ée]veloppeuse|responsable|analyste|gestionnaire|"
    r"coordinateur|coordinatrice|formateur|formatrice|administrateur|"
    r"administratrice|sp[ée]cialiste|technicien(?:ne)?|charg[ée](?:e)?"
    r")\b"
)
# Only scan near the top of the document -- a candidate's own name always
# appears there (either as an explicit "Nom:" label or as the CV's title
# line), and scanning the whole document risks matching an unrelated
# capitalized 2-4 word phrase deeper in (e.g. a former employer's name).
_NAME_SCAN_LINE_LIMIT = 10


def _is_name_shaped(line: str) -> re.Match[str] | None:
    """A capitalized 2-4 word line that doesn't read as a job title."""
    match = _NAME_LINE_REGEX.match(line)
    if match and not _JOB_TITLE_WORD_REGEX.search(line):
        return match
    return None


def _detect_candidate_name(text: str) -> str | None:
    """Expects `text` already run through `mask_contact_info` -- contact
    lines are identified by their `[EMAIL]`/`[PHONE]` placeholders rather
    than by re-matching the raw regexes.
    """
    lines = text.splitlines()[:_NAME_SCAN_LINE_LIMIT]

    for line in lines:
        label_match = _NAME_LABEL_REGEX.match(line)
        if label_match and label_match.group(1).strip():
            return label_match.group(1).strip()

    # Most reliable signal: every real CV fixture in this project puts the
    # candidate's name on the line immediately above their email/phone,
    # regardless of what headline (job title, "Curriculum Vitae"...) may
    # sit further up the page. Far more robust than "first capitalized
    # line found" -- that heuristic breaks the moment a job-title headline
    # precedes the name.
    contact_line_index = next(
        (i for i, line in enumerate(lines) if "[EMAIL]" in line or "[PHONE]" in line),
        None,
    )
    if contact_line_index is not None and contact_line_index > 0:
        candidate = lines[contact_line_index - 1].strip()
        name_match = _is_name_shaped(candidate)
        if name_match:
            return name_match.group(1)

    # Fallback: first name-shaped line near the top -- used when no
    # contact line was found at all in the scanned window.
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        line_match = _is_name_shaped(stripped)
        if line_match:
            return line_match.group(1)

    return None


def mask_cv_pii(text: str) -> tuple[str, str | None]:
    """CV-only PII masking: `mask_contact_info` plus a best-effort
    candidate-name heuristic (a "Nom"/"Nom et Prénom" label, or a
    capitalized 2-4 word line near the top of the document -- this
    project's CVs are French-language). Every occurrence of the detected
    name is replaced with `[NOM]`.

    Deliberately NOT applied to TDR text (see `mask_contact_info`'s callers
    in extract.py) -- TDRs describe roles to be staffed, not named
    individuals, and this generic name-shaped heuristic risks mangling
    mission_title/client extraction there.

    Returns (masked_text, detected_name) -- detected_name is None if no
    name-shaped line was found, letting the caller fall back to whatever
    the LLM itself extracts from the masked prompt.
    """
    masked = mask_contact_info(text)
    name = _detect_candidate_name(masked)
    if name:
        masked = re.compile(re.escape(name), re.IGNORECASE).sub("[NOM]", masked)
    return masked, name

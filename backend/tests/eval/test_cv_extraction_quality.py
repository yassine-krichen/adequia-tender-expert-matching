"""Live CV extraction quality regression suite.

Not part of the default `uv run pytest` run (see `addopts` in pyproject.toml)
-- these hit real LLM providers against real documents in docs/cvs/synthetic/,
which costs real free-tier quota and real wall-clock time. Run explicitly:

    uv run pytest -m eval

Each fixture in fixtures/cv/*.json is a hand-verified answer key, built by
actually reading the real source document once. Adding a new document: read
it once, write a fixture describing what a correct extraction looks like,
then this suite checks every future retrieval/prompt change against every
fixture that came before it -- no re-reading documents by eye each time.

Mirrors test_tdr_extraction_quality.py's structure and normalization
approach, adapted to CandidateCV's richer field set (education, experience,
certifications, languages, total_years_experience).
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.domain.cv import CandidateCV, Certification, Education, Experience, LanguageProficiency
from app.features.pipeline.nodes.extract import extract_cv
from app.features.pipeline.nodes.ingest import extract_raw_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "cv"


def _load_fixtures() -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(_FIXTURES_DIR.glob("*.json"))]


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-·]+", "", text.lower())


def _contains(actual: str | None, expected_substring: str | None) -> bool:
    if expected_substring is None:
        return True
    if actual is None:
        return False
    return _normalize(expected_substring) in _normalize(actual)


def _find_education_match(expected: dict[str, Any], actual: list[Education]) -> Education | None:
    for edu in actual:
        if _contains(edu.degree, expected.get("degree_contains")) and _contains(
            edu.institution, expected.get("institution_contains")
        ):
            return edu
    return None


def _find_experience_match(expected: dict[str, Any], actual: list[Experience]) -> Experience | None:
    for exp in actual:
        if _contains(exp.title, expected.get("title_contains")) and _contains(
            exp.employer, expected.get("employer_contains")
        ):
            return exp
    return None


def _find_certification_match(expected: dict[str, Any], actual: list[Certification]) -> Certification | None:
    for cert in actual:
        if _contains(cert.name, expected.get("name_contains")):
            return cert
    return None


def _find_language_match(expected: dict[str, Any], actual: list[LanguageProficiency]) -> LanguageProficiency | None:
    for lang in actual:
        if _contains(lang.language, expected.get("language_contains")) and _contains(
            lang.level, expected.get("level_contains")
        ):
            return lang
    return None


def _format_report(fixture_name: str, expected: dict[str, Any], cv: CandidateCV) -> str:
    lines = [f"Extraction mismatch for {fixture_name}", "", f"full_name: {cv.full_name!r}", ""]

    lines.append("Expected education:")
    for exp_edu in expected.get("education", []):
        match = _find_education_match(exp_edu, cv.education)
        status = "OK" if match else "MISSING"
        lines.append(
            f"  [{status}] degree~{exp_edu.get('degree_contains')!r} "
            f"institution~{exp_edu.get('institution_contains')!r} year={exp_edu.get('graduation_year')}"
        )
    lines.append("Actual education:")
    for edu in cv.education:
        lines.append(f"  - {edu.degree!r} @ {edu.institution!r} year={edu.graduation_year!r}")

    lines.append("")
    lines.append("Expected experience:")
    for exp_exp in expected.get("experience", []):
        match = _find_experience_match(exp_exp, cv.experience)
        status = "OK" if match else "MISSING"
        lines.append(
            f"  [{status}] title~{exp_exp.get('title_contains')!r} "
            f"employer~{exp_exp.get('employer_contains')!r} "
            f"start={exp_exp.get('start_year')} end={exp_exp.get('end_year')}"
        )
    lines.append("Actual experience:")
    for exp in cv.experience:
        lines.append(
            f"  - {exp.title!r} @ {exp.employer!r} start={exp.start_date!r} end={exp.end_date!r}"
        )

    lines.append("")
    lines.append("Expected certifications:")
    for exp_cert in expected.get("certifications", []):
        match = _find_certification_match(exp_cert, cv.certifications)
        status = "OK" if match else "MISSING"
        lines.append(f"  [{status}] name~{exp_cert.get('name_contains')!r}")
    lines.append("Actual certifications:")
    for cert in cv.certifications:
        lines.append(f"  - {cert.name!r}")

    lines.append("")
    lines.append("Expected languages:")
    for exp_lang in expected.get("languages", []):
        match = _find_language_match(exp_lang, cv.languages)
        status = "OK" if match else "MISSING"
        lines.append(
            f"  [{status}] language~{exp_lang.get('language_contains')!r} level~{exp_lang.get('level_contains')!r}"
        )
    lines.append("Actual languages:")
    for lang in cv.languages:
        lines.append(f"  - {lang.language!r} level={lang.level!r}")

    lines.append("")
    lines.append(f"total_years_experience: actual={cv.total_years_experience}")

    return "\n".join(lines)


@pytest.mark.eval
@pytest.mark.parametrize("fixture", _load_fixtures(), ids=lambda f: Path(f["source_file"]).stem)
def test_cv_extraction_matches_hand_verified_fields(fixture: dict[str, Any]) -> None:
    source_path = _REPO_ROOT / fixture["source_file"]
    raw_text = extract_raw_text(source_path.read_bytes(), source_path.name)

    router = ModelRouter(get_settings())
    cv = extract_cv(
        raw_text,
        candidate_id="eval-run",
        source_file_path=source_path.name,
        router=router,
    )

    expected = fixture["expected"]
    report = _format_report(source_path.name, expected, cv)

    assert _contains(cv.full_name, expected.get("full_name_contains")), report

    for exp_edu in expected.get("education", []):
        match = _find_education_match(exp_edu, cv.education)
        assert match is not None, report
        if exp_edu.get("graduation_year") is not None:
            assert match.graduation_year == exp_edu["graduation_year"], report

    for exp_exp in expected.get("experience", []):
        match = _find_experience_match(exp_exp, cv.experience)
        assert match is not None, report
        if exp_exp.get("start_year") is not None:
            assert match.start_date.year == exp_exp["start_year"], report
        if "end_year" in exp_exp:
            if exp_exp["end_year"] is None:
                assert match.end_date is None, report
            else:
                assert match.end_date is not None and match.end_date.year == exp_exp["end_year"], report

    for exp_cert in expected.get("certifications", []):
        assert _find_certification_match(exp_cert, cv.certifications) is not None, report

    for exp_lang in expected.get("languages", []):
        assert _find_language_match(exp_lang, cv.languages) is not None, report

    if "total_years_experience_min" in expected:
        assert cv.total_years_experience >= expected["total_years_experience_min"], report
    if "total_years_experience_max" in expected:
        assert cv.total_years_experience <= expected["total_years_experience_max"], report

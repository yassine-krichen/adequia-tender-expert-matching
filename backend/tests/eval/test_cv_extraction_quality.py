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
from tests.eval._scoring import _TypeCounts

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "cv"

# Regression gate threshold from the sprint plan's acceptance criteria
# ("extraction F1 drops >3pts"). Update deliberately when the gold set
# intentionally grows/shrinks -- not silently, and not to paper over a real
# regression. Real baseline measured by running this suite once, live,
# against all 11 synthetic CVs in docs/cvs/synthetic/ (ADQ-33, see
# docs/04-evaluation-metrics.md): aggregate F1=0.978 across full_name,
# education, education_graduation_year, experience, experience_dates,
# certifications, languages, total_years_experience. The two real misses at
# that run were both on youssef-kammoun.pdf (a graduation_year the model
# didn't extract, and a still-employed vs. ended role date mismatch).
_BASELINE_CV_F1 = 0.978
_REGRESSION_TOLERANCE = 0.03


def _load_fixtures() -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(_FIXTURES_DIR.glob("*.json"))
    ]


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


def _find_certification_match(
    expected: dict[str, Any], actual: list[Certification]
) -> Certification | None:
    for cert in actual:
        if _contains(cert.name, expected.get("name_contains")):
            return cert
    return None


def _find_language_match(
    expected: dict[str, Any], actual: list[LanguageProficiency]
) -> LanguageProficiency | None:
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
                assert (
                    match.end_date is not None and match.end_date.year == exp_exp["end_year"]
                ), report

    for exp_cert in expected.get("certifications", []):
        assert _find_certification_match(exp_cert, cv.certifications) is not None, report

    for exp_lang in expected.get("languages", []):
        assert _find_language_match(exp_lang, cv.languages) is not None, report

    if "total_years_experience_min" in expected:
        assert cv.total_years_experience >= expected["total_years_experience_min"], report
    if "total_years_experience_max" in expected:
        assert cv.total_years_experience <= expected["total_years_experience_max"], report


@pytest.mark.eval
def test_cv_extraction_field_level_f1_regression() -> None:
    """ADQ-30's DeepEval-style regression gate. Reuses the same per-field
    matchers (`_find_education_match`/`_find_experience_match`/
    `_find_certification_match`/`_find_language_match`) the per-fixture test
    above uses, to accumulate TP/FP/FN across ALL 11 fixtures into per-field
    types, then asserts the aggregate F1 hasn't regressed past
    `_REGRESSION_TOLERANCE` below `_BASELINE_CV_F1`.

    Kept entirely separate from the per-fixture parametrized test above --
    that stays untouched for its failure-localization value (which fixture,
    which field broke); this one gate is what CI actually asserts on.
    """
    router = ModelRouter(get_settings())
    per_field_counts: dict[str, _TypeCounts] = {
        "full_name": _TypeCounts(),
        "education": _TypeCounts(),
        "education_graduation_year": _TypeCounts(),
        "experience": _TypeCounts(),
        "experience_dates": _TypeCounts(),
        "certifications": _TypeCounts(),
        "languages": _TypeCounts(),
        "total_years_experience": _TypeCounts(),
    }
    detail_lines: list[str] = []

    for fixture in _load_fixtures():
        source_path = _REPO_ROOT / fixture["source_file"]
        raw_text = extract_raw_text(source_path.read_bytes(), source_path.name)
        cv = extract_cv(
            raw_text, candidate_id="eval-run", source_file_path=source_path.name, router=router
        )
        expected = fixture["expected"]
        name = source_path.name

        if _contains(cv.full_name, expected.get("full_name_contains")):
            per_field_counts["full_name"].true_positives += 1
        else:
            per_field_counts["full_name"].false_negatives += 1
            detail_lines.append(f"{name}: full_name mismatch actual={cv.full_name!r}")

        matched_edu_ids = set()
        for exp_edu in expected.get("education", []):
            match = _find_education_match(exp_edu, cv.education)
            if match is None:
                per_field_counts["education"].false_negatives += 1
                detail_lines.append(f"{name}: MISSING education {exp_edu.get('degree_contains')!r}")
                continue
            per_field_counts["education"].true_positives += 1
            matched_edu_ids.add(id(match))
            if exp_edu.get("graduation_year") is not None:
                if match.graduation_year == exp_edu["graduation_year"]:
                    per_field_counts["education_graduation_year"].true_positives += 1
                else:
                    per_field_counts["education_graduation_year"].false_negatives += 1
                    detail_lines.append(
                        f"{name}: education graduation_year mismatch "
                        f"expected={exp_edu['graduation_year']} actual={match.graduation_year}"
                    )
        extra_edu = [e for e in cv.education if id(e) not in matched_edu_ids]
        per_field_counts["education"].false_positives += len(extra_edu)

        matched_exp_ids = set()
        for exp_exp in expected.get("experience", []):
            match = _find_experience_match(exp_exp, cv.experience)
            if match is None:
                per_field_counts["experience"].false_negatives += 1
                detail_lines.append(f"{name}: MISSING experience {exp_exp.get('title_contains')!r}")
                continue
            per_field_counts["experience"].true_positives += 1
            matched_exp_ids.add(id(match))

            dates_expected = "start_year" in exp_exp or "end_year" in exp_exp
            if dates_expected:
                start_ok = (
                    exp_exp.get("start_year") is None
                    or match.start_date.year == exp_exp["start_year"]
                )
                if "end_year" in exp_exp:
                    end_ok = (
                        match.end_date is None
                        if exp_exp["end_year"] is None
                        else (
                            match.end_date is not None
                            and match.end_date.year == exp_exp["end_year"]
                        )
                    )
                else:
                    end_ok = True
                if start_ok and end_ok:
                    per_field_counts["experience_dates"].true_positives += 1
                else:
                    per_field_counts["experience_dates"].false_negatives += 1
                    detail_lines.append(
                        f"{name}: experience dates mismatch for {exp_exp.get('title_contains')!r} "
                        f"expected start={exp_exp.get('start_year')} end={exp_exp.get('end_year')} "
                        f"actual start={match.start_date.year} end={match.end_date}"
                    )
        extra_exp = [e for e in cv.experience if id(e) not in matched_exp_ids]
        per_field_counts["experience"].false_positives += len(extra_exp)

        matched_cert_ids = set()
        for exp_cert in expected.get("certifications", []):
            match = _find_certification_match(exp_cert, cv.certifications)
            if match is None:
                per_field_counts["certifications"].false_negatives += 1
                detail_lines.append(
                    f"{name}: MISSING certification {exp_cert.get('name_contains')!r}"
                )
                continue
            per_field_counts["certifications"].true_positives += 1
            matched_cert_ids.add(id(match))
        extra_cert = [c for c in cv.certifications if id(c) not in matched_cert_ids]
        per_field_counts["certifications"].false_positives += len(extra_cert)

        matched_lang_ids = set()
        for exp_lang in expected.get("languages", []):
            match = _find_language_match(exp_lang, cv.languages)
            if match is None:
                per_field_counts["languages"].false_negatives += 1
                detail_lines.append(
                    f"{name}: MISSING language {exp_lang.get('language_contains')!r}"
                )
                continue
            per_field_counts["languages"].true_positives += 1
            matched_lang_ids.add(id(match))
        extra_lang = [lang for lang in cv.languages if id(lang) not in matched_lang_ids]
        per_field_counts["languages"].false_positives += len(extra_lang)

        if "total_years_experience_min" in expected or "total_years_experience_max" in expected:
            within_min = (
                "total_years_experience_min" not in expected
                or cv.total_years_experience >= expected["total_years_experience_min"]
            )
            within_max = (
                "total_years_experience_max" not in expected
                or cv.total_years_experience <= expected["total_years_experience_max"]
            )
            if within_min and within_max:
                per_field_counts["total_years_experience"].true_positives += 1
            else:
                per_field_counts["total_years_experience"].false_negatives += 1
                detail_lines.append(
                    f"{name}: total_years_experience out of expected range "
                    f"actual={cv.total_years_experience}"
                )

    aggregate = _TypeCounts(
        true_positives=sum(c.true_positives for c in per_field_counts.values()),
        false_positives=sum(c.false_positives for c in per_field_counts.values()),
        false_negatives=sum(c.false_negatives for c in per_field_counts.values()),
    )

    summary_lines = [
        f"{field}: precision={counts.precision:.2f} recall={counts.recall:.2f} f1={counts.f1:.2f} "
        f"(tp={counts.true_positives} fp={counts.false_positives} fn={counts.false_negatives})"
        for field, counts in per_field_counts.items()
    ]
    report = (
        f"CV field-level F1 regression check -- aggregate F1={aggregate.f1:.3f} "
        f"(baseline={_BASELINE_CV_F1}, tolerance={_REGRESSION_TOLERANCE})\n"
        + "\n".join(summary_lines)
        + "\n"
        + "\n".join(detail_lines)
    )
    print(report)

    assert aggregate.f1 >= _BASELINE_CV_F1 - _REGRESSION_TOLERANCE, report

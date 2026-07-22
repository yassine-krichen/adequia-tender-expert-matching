"""Synthetic anomaly-injection eval for the four rule-based checks in
`detect_anomalies.py` -- `employment_gap`, `date_overlap`,
`expired_certification`, `age_graduation_implausibility`.

Not part of the default `uv run pytest` run (see `addopts` in pyproject.toml)
-- marked `@pytest.mark.eval` for organizational consistency with the rest of
`tests/eval/`, even though this specific suite is pure Python (no LLM, no DB,
no network) and costs zero quota.

Methodology per docs/04-evaluation-metrics.md's "Synthetic anomaly injection
-- design" section: for each clean baseline CV, generate a variant with
exactly one injected anomaly via `.model_copy()`, then run the matching
`check_*` function against both the clean and injected version. The clean
run is the false-positive side (expect no anomaly of that type); the
injected run is the true-positive side (expect exactly one). Accumulated
into precision/recall/F1 per type plus an overall false-positive rate on
the clean baselines -- the two metrics docs/04-evaluation-metrics.md
requires for anomaly detection.

Measurement only, no hard CI gate -- see the assertion at the bottom.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from app.domain.cv import CandidateCV, Certification, Education, Experience
from app.domain.matching import Anomaly, AnomalyType
from app.features.pipeline.nodes.detect_anomalies import (
    _DATE_OVERLAP_TOLERANCE_DAYS,
    _EMPLOYMENT_GAP_THRESHOLD_DAYS,
    _MAX_PLAUSIBLE_GRADUATION_AGE,
    _MIN_PLAUSIBLE_GRADUATION_AGE,
    check_age_at_graduation,
    check_date_overlaps,
    check_employment_gaps,
    check_expired_certifications,
)
from tests.eval._scoring import _TypeCounts

# --- builder helpers, mirroring test_detect_anomalies.py's style -----------


def _experience(
    *,
    title: str = "Chef de projet",
    employer: str = "ST2i",
    start_date: date,
    end_date: date | None,
    source_span: str = "span",
) -> Experience:
    return Experience(
        title=title, employer=employer, start_date=start_date, end_date=end_date, source_span=source_span
    )


def _education(
    *,
    degree: str = "Master en Génie Logiciel",
    graduation_year: int | None,
    source_span: str = "edu-span",
) -> Education:
    return Education(
        degree=degree, institution="INSAT", graduation_year=graduation_year, source_span=source_span
    )


def _certification(
    *, name: str = "PMP", expiry_date: date | None, source_span: str = "cert-span"
) -> Certification:
    return Certification(name=name, expiry_date=expiry_date, source_span=source_span)


def _cv(
    *,
    birth_date: date,
    experience: list[Experience],
    certifications: list[Certification],
    education: list[Education],
) -> CandidateCV:
    return CandidateCV(
        candidate_id="c1",
        full_name="Test Candidate",
        education=education,
        certifications=certifications,
        experience=experience,
        languages=[],
        birth_date=birth_date,
        raw_skills=[],
        total_years_experience=5.0,
        raw_text="raw",
        source_file_path="cv.pdf",
    )


@dataclass(frozen=True)
class _Baseline:
    """One clean, internally-consistent candidate: 3 sequential experience
    entries (small gaps well under the employment-gap threshold, no
    overlaps), a certification, and education/birth_date pair with a
    plausible age at graduation.
    """

    name: str
    cv: CandidateCV


# 5 varied clean baselines: different eras, a currently-ongoing last role,
# a future-dated cert vs. no-expiry cert, and one candidate with a second
# education entry that has no graduation_year at all.
_BASELINES = [
    _Baseline(
        "junior_no_cert_expiry",
        _cv(
            birth_date=date(1990, 1, 1),
            experience=[
                _experience(start_date=date(2015, 1, 1), end_date=date(2016, 1, 1)),
                _experience(start_date=date(2016, 1, 15), end_date=date(2018, 1, 1)),
                _experience(start_date=date(2018, 1, 15), end_date=date(2020, 1, 1)),
            ],
            certifications=[_certification(expiry_date=None)],
            education=[_education(graduation_year=2014)],
        ),
    ),
    _Baseline(
        "mid_career_future_cert_expiry",
        _cv(
            birth_date=date(1985, 6, 15),
            experience=[
                _experience(start_date=date(2010, 1, 1), end_date=date(2012, 1, 1)),
                _experience(start_date=date(2012, 2, 1), end_date=date(2015, 1, 1)),
                _experience(start_date=date(2015, 2, 1), end_date=date(2019, 1, 1)),
            ],
            certifications=[_certification(expiry_date=date.today() + timedelta(days=200))],
            education=[_education(graduation_year=2009)],
        ),
    ),
    _Baseline(
        "recent_grad_currently_employed",
        _cv(
            birth_date=date(1994, 3, 1),
            experience=[
                _experience(start_date=date(2019, 1, 1), end_date=date(2020, 6, 1)),
                _experience(start_date=date(2020, 7, 1), end_date=date(2022, 1, 1)),
                _experience(start_date=date(2022, 2, 1), end_date=None),
            ],
            certifications=[_certification(expiry_date=None)],
            education=[_education(graduation_year=2018)],
        ),
    ),
    _Baseline(
        "senior_long_career_future_cert_expiry",
        _cv(
            birth_date=date(1980, 1, 1),
            experience=[
                _experience(start_date=date(2005, 1, 1), end_date=date(2009, 1, 1)),
                _experience(start_date=date(2009, 2, 1), end_date=date(2015, 1, 1)),
                _experience(start_date=date(2015, 2, 1), end_date=date(2023, 1, 1)),
            ],
            certifications=[_certification(expiry_date=date.today() + timedelta(days=1000))],
            education=[_education(graduation_year=2004)],
        ),
    ),
    _Baseline(
        "second_education_without_graduation_year",
        _cv(
            birth_date=date(1992, 1, 1),
            experience=[
                _experience(start_date=date(2017, 1, 1), end_date=date(2018, 6, 1)),
                _experience(start_date=date(2018, 7, 1), end_date=date(2020, 1, 1)),
                _experience(start_date=date(2020, 2, 1), end_date=date(2022, 6, 1)),
            ],
            certifications=[_certification(expiry_date=None)],
            education=[
                _education(degree="Licence", graduation_year=None),
                _education(degree="Master en Génie Logiciel", graduation_year=2016),
            ],
        ),
    ),
]


# --- injection functions -----------------------------------------------


def inject_employment_gap(experience: list[Experience]) -> list[Experience]:
    """Removes the middle experience entry, surrounding dates untouched, per
    docs/04-evaluation-metrics.md's injection method -- the surrounding
    entries' spacing (a few weeks) opens a real multi-year gap once the
    middle entry that used to bridge them is gone.

    This is a far-from-boundary case (the resulting gap is 1.5+ years, well
    past _EMPLOYMENT_GAP_THRESHOLD_DAYS): it exercises the check but can't by
    itself tell us whether the threshold constant needs retuning. See
    `inject_employment_gap_near_threshold` for the near-boundary companion.
    """
    ordered = sorted(experience, key=lambda exp: exp.start_date)
    if len(ordered) < 3:
        raise ValueError("need >=3 experience entries to remove a middle one")
    return [ordered[0], *ordered[2:]]


def inject_employment_gap_near_threshold(experience: list[Experience]) -> list[Experience]:
    """Shifts the last entry's start_date so the gap to the previous entry's
    end_date is exactly _EMPLOYMENT_GAP_THRESHOLD_DAYS + 10 days -- a
    threshold+margin test mirroring `inject_date_overlap`'s style, so the
    result actually informs whether _EMPLOYMENT_GAP_THRESHOLD_DAYS needs
    retuning (unlike the far-from-boundary entry-removal case above).
    """
    ordered = sorted(experience, key=lambda exp: exp.start_date)
    if len(ordered) < 2:
        raise ValueError("need >=2 experience entries to open a near-threshold gap")
    *rest, last = ordered
    previous = rest[-1]
    assert previous.end_date is not None
    shifted_start = previous.end_date + timedelta(days=_EMPLOYMENT_GAP_THRESHOLD_DAYS + 10)
    shifted_last = last.model_copy(update={"start_date": shifted_start})
    return [*rest, shifted_last]


def inject_date_overlap(experience: list[Experience]) -> list[Experience]:
    """Shifts the middle entry's start_date to land inside the first entry's
    span, overlapping it by more than _DATE_OVERLAP_TOLERANCE_DAYS. Only the
    start_date moves (end_date untouched), so the shifted entry still ends
    before the third entry starts -- exactly one overlap is introduced, not
    a cascade across all three entries.
    """
    ordered = sorted(experience, key=lambda exp: exp.start_date)
    if len(ordered) < 2:
        raise ValueError("need >=2 experience entries to create an overlap")
    first, middle, *rest = ordered
    assert first.end_date is not None
    overlapping_start = first.end_date - timedelta(days=_DATE_OVERLAP_TOLERANCE_DAYS + 10)
    shifted_middle = middle.model_copy(update={"start_date": overlapping_start})
    return [first, shifted_middle, *rest]


def inject_expired_certification(certifications: list[Certification]) -> list[Certification]:
    """Sets one certification's expiry_date into the past, per
    docs/04-evaluation-metrics.md's injection method.
    """
    if not certifications:
        raise ValueError("need >=1 certification to expire")
    first, *rest = certifications
    expired = first.model_copy(update={"expiry_date": date.today() - timedelta(days=30)})
    return [expired, *rest]


def inject_implausible_graduation_age(birth_date: date, education: list[Education]) -> list[Education]:
    """Sets a graduation_year on one education entry so age-at-graduation
    falls just below _MIN_PLAUSIBLE_GRADUATION_AGE.
    """
    if not education:
        raise ValueError("need >=1 education entry to make implausible")
    target, *rest = education
    implausible_year = birth_date.year + _MIN_PLAUSIBLE_GRADUATION_AGE - 1
    injected = target.model_copy(update={"graduation_year": implausible_year})
    return [injected, *rest]


# --- eval harness ------------------------------------------------------


@pytest.mark.eval
def test_rule_based_anomaly_detection_precision_recall_f1() -> None:
    per_type_counts: dict[AnomalyType, _TypeCounts] = {
        AnomalyType.employment_gap: _TypeCounts(),
        AnomalyType.date_overlap: _TypeCounts(),
        AnomalyType.expired_certification: _TypeCounts(),
        AnomalyType.age_graduation_implausibility: _TypeCounts(),
    }
    detail_lines: list[str] = []
    clean_check_count = 0
    clean_false_positive_count = 0

    for baseline in _BASELINES:
        cv = baseline.cv
        assert cv.birth_date is not None  # every baseline sets one -- narrows date | None

        cases: list[tuple[AnomalyType, str, list[Anomaly], list[Anomaly]]] = [
            (
                AnomalyType.employment_gap,
                "far_from_threshold",
                check_employment_gaps(cv.experience),
                check_employment_gaps(inject_employment_gap(cv.experience)),
            ),
            (
                AnomalyType.employment_gap,
                "near_threshold(+10d)",
                check_employment_gaps(cv.experience),
                check_employment_gaps(inject_employment_gap_near_threshold(cv.experience)),
            ),
            (
                AnomalyType.date_overlap,
                "near_threshold(+10d)",
                check_date_overlaps(cv.experience),
                check_date_overlaps(inject_date_overlap(cv.experience)),
            ),
            (
                AnomalyType.expired_certification,
                "expired",
                check_expired_certifications(cv.certifications),
                check_expired_certifications(inject_expired_certification(cv.certifications)),
            ),
            (
                AnomalyType.age_graduation_implausibility,
                "near_threshold(-1y)",
                check_age_at_graduation(cv.birth_date, cv.education),
                check_age_at_graduation(
                    cv.birth_date, inject_implausible_graduation_age(cv.birth_date, cv.education)
                ),
            ),
        ]

        for anomaly_type, variant, clean_anomalies, injected_anomalies in cases:
            clean_matches = [a for a in clean_anomalies if a.type == anomaly_type]
            injected_matches = [a for a in injected_anomalies if a.type == anomaly_type]
            counts = per_type_counts[anomaly_type]

            clean_check_count += 1
            if clean_matches:
                clean_false_positive_count += 1
                counts.false_positives += 1

            if injected_matches:
                counts.true_positives += 1
            else:
                counts.false_negatives += 1

            detail_lines.append(
                f"{baseline.name} [{anomaly_type.value}/{variant}]: "
                f"clean_flags={len(clean_matches)} injected_flags={len(injected_matches)}"
            )

    overall_false_positive_rate = clean_false_positive_count / clean_check_count

    summary_lines = [
        f"{anomaly_type.value}: precision={counts.precision:.2f} recall={counts.recall:.2f} "
        f"f1={counts.f1:.2f} (tp={counts.true_positives} fp={counts.false_positives} "
        f"fn={counts.false_negatives})"
        for anomaly_type, counts in per_type_counts.items()
    ]

    report = (
        "Rule-based anomaly detection eval over "
        f"{len(_BASELINES)} synthetic baselines\n"
        f"Overall false-positive rate on clean baselines: {overall_false_positive_rate:.2f} "
        f"({clean_false_positive_count}/{clean_check_count})\n"
        "Current threshold constants: "
        f"_EMPLOYMENT_GAP_THRESHOLD_DAYS={_EMPLOYMENT_GAP_THRESHOLD_DAYS} "
        f"_DATE_OVERLAP_TOLERANCE_DAYS={_DATE_OVERLAP_TOLERANCE_DAYS} "
        f"_MIN_PLAUSIBLE_GRADUATION_AGE={_MIN_PLAUSIBLE_GRADUATION_AGE} "
        f"_MAX_PLAUSIBLE_GRADUATION_AGE={_MAX_PLAUSIBLE_GRADUATION_AGE}\n"
        + "\n".join(summary_lines)
        + "\n"
        + "\n".join(detail_lines)
    )
    print(report)

    # Sanity that the harness didn't silently break, not a quality gate --
    # this story is measurement-only (no hard CI threshold). The report
    # above is the actual payoff, read by a human to decide whether the
    # threshold constants need retuning.
    assert report
    assert all(
        counts.true_positives + counts.false_negatives > 0 for counts in per_type_counts.values()
    )

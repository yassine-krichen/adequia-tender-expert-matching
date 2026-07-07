from datetime import date

from app.database.models import CV as CVModel
from app.domain.cv import CandidateCV, Experience
from app.domain.tdr import ExpertPosition
from app.features.matching.coarse_retrieval import (
    _build_position_query_text,
    _sector_overlap_boost,
    _years_proximity_boost,
    rerank_shortlist_pool,
)


def _cv(*, sector: str | None = None, total_years_experience: float = 5.0) -> CandidateCV:
    return CandidateCV(
        candidate_id="c1",
        full_name="Test Candidate",
        education=[],
        certifications=[],
        experience=(
            [
                Experience(
                    title="Chef de projet",
                    employer="ST2i",
                    sector=sector,
                    start_date=date(2018, 1, 1),
                    source_span="span",
                )
            ]
            if sector is not None
            else []
        ),
        languages=[],
        raw_skills=["Gestion de projet"],
        total_years_experience=total_years_experience,
        raw_text="raw",
        source_file_path="cv.pdf",
    )


def _position(
    *, required_sector_experience: str | None = None, minimum_years_experience: float | None = None
) -> ExpertPosition:
    return ExpertPosition(
        position_id="p1",
        position_title="Chef de projet",
        required_skills=["Gestion de projet"],
        required_sector_experience=required_sector_experience,
        minimum_years_experience=minimum_years_experience,
        source_span="span",
    )


def test_build_position_query_text_combines_title_skills_and_sector() -> None:
    position = _position(required_sector_experience="Secteur bancaire")
    text = _build_position_query_text(position)

    assert "Chef de projet" in text
    assert "Gestion de projet" in text
    assert "Secteur bancaire" in text


def test_sector_overlap_boost_is_zero_when_position_has_no_sector_requirement() -> None:
    assert _sector_overlap_boost(_cv(sector="Banque"), _position()) == 0.0


def test_sector_overlap_boost_applies_on_case_insensitive_substring_match() -> None:
    cv = _cv(sector="secteur bancaire")
    position = _position(required_sector_experience="Bancaire")

    assert _sector_overlap_boost(cv, position) > 0.0


def test_sector_overlap_boost_is_zero_when_no_experience_sector_matches() -> None:
    cv = _cv(sector="Télécom")
    position = _position(required_sector_experience="Bancaire")

    assert _sector_overlap_boost(cv, position) == 0.0


def test_years_proximity_boost_penalizes_under_qualified_candidates() -> None:
    cv = _cv(total_years_experience=2.0)
    position = _position(minimum_years_experience=5.0)

    assert _years_proximity_boost(cv, position) < 0.0


def test_years_proximity_boost_rewards_but_caps_over_qualified_candidates() -> None:
    modestly_over = _years_proximity_boost(_cv(total_years_experience=6.0), _position(minimum_years_experience=5.0))
    hugely_over = _years_proximity_boost(_cv(total_years_experience=30.0), _position(minimum_years_experience=5.0))

    assert modestly_over > 0.0
    assert hugely_over == modestly_over or hugely_over > modestly_over
    assert hugely_over <= 0.15  # capped, doesn't blow past the sector boost


def test_rerank_shortlist_pool_prefers_sector_match_at_equal_similarity() -> None:
    position = _position(required_sector_experience="Bancaire")
    matching_cv_row = CVModel(extracted_json=_cv(sector="Bancaire").model_dump(mode="json"))
    other_cv_row = CVModel(extracted_json=_cv(sector="Télécom").model_dump(mode="json"))

    ranked = rerank_shortlist_pool([(other_cv_row, 0.8), (matching_cv_row, 0.8)], position)

    assert ranked[0][0] is matching_cv_row

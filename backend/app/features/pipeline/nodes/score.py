import math
import re
from collections.abc import Sequence
from datetime import date

from langchain_core.embeddings import Embeddings

from app.domain.cv import CandidateCV, NormalizedSkill
from app.domain.matching import SubScores
from app.domain.tdr import ExpertPosition
from app.features.pipeline.state import PipelineState

# Hard filters only -- LLM judgment and historical_decisions memory
# calibration are deferred to Sprint 3 (ADQ-19). See docs/03-agent-pipeline.md
# node 4.
_DIPLOMA_LEVEL_KEYWORDS: dict[int, tuple[str, ...]] = {
    3: ("licence", "bachelor"),
    5: ("master", "ingénieur", "ingenieur", "mastère", "mastere"),
    8: ("doctorat", "phd", "doctorate"),
}

# ADQ-16: only skill_score and sector_score are computed this sprint (see
# domain/matching.py SubScores docstring). Fixed weights, not a real
# per-criterion weight map -- ExpertPosition.evaluation_weight is a single
# scalar, not something that splits meaningfully across two criteria yet.
_SKILL_WEIGHT = 0.6
_SECTOR_WEIGHT = 0.4


def _extract_bac_level(text: str) -> int | None:
    match = re.search(r"bac\s*\+\s*(\d+)", text.lower())
    return int(match.group(1)) if match else None


def _diploma_satisfied(cv: CandidateCV, mandatory_diploma: str) -> bool:
    """Lenient heuristic, not an exact match -- free-form French diploma
    strings ("Bac+5", "Ingénieur", "Master en ...") don't line up with a
    CV's own free-form degree text reliably enough for anything stricter.
    """
    candidate_texts = [f"{edu.degree} {edu.field or ''}".lower() for edu in cv.education]

    required_level = _extract_bac_level(mandatory_diploma)
    if required_level is not None:
        return any(
            level >= required_level and keyword in text
            for level, keywords in _DIPLOMA_LEVEL_KEYWORDS.items()
            for keyword in keywords
            for text in candidate_texts
        )

    required_keywords = {word for word in re.findall(r"\w+", mandatory_diploma.lower()) if len(word) > 2}
    return any(required_keywords & set(re.findall(r"\w+", text)) for text in candidate_texts)


def _years_satisfied(cv: CandidateCV, minimum_years_experience: float | None) -> bool:
    if minimum_years_experience is None:
        return True
    return cv.total_years_experience >= minimum_years_experience


def _missing_certifications(cv: CandidateCV, required_certifications: list[str]) -> list[str]:
    today = date.today()
    missing: list[str] = []
    for required in required_certifications:
        required_lower = required.strip().lower()
        found = any(
            (required_lower in cert.name.lower() or cert.name.lower() in required_lower)
            and (cert.expiry_date is None or cert.expiry_date >= today)
            for cert in cv.certifications
        )
        if not found:
            missing.append(required)
    return missing


def check_hard_filters(cv: CandidateCV, position: ExpertPosition) -> tuple[bool, list[str]]:
    """ADQ-15. Returns (hard_filter_passed, human-readable failure reasons)."""
    failures: list[str] = []

    if position.mandatory_diploma and not _diploma_satisfied(cv, position.mandatory_diploma):
        failures.append(f"Missing mandatory diploma: {position.mandatory_diploma}")

    if not _years_satisfied(cv, position.minimum_years_experience):
        failures.append(
            f"Insufficient experience: {cv.total_years_experience:.1f} years "
            f"(minimum {position.minimum_years_experience})"
        )

    for cert_name in _missing_certifications(cv, position.required_certifications):
        failures.append(f"Missing or expired certification: {cert_name}")

    return not failures, failures


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = float(sum(x * y for x, y in zip(a, b, strict=True)))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _skill_score(
    normalized_position_skills: list[NormalizedSkill],
    normalized_cv_skills: list[NormalizedSkill],
) -> float:
    """Coverage ratio of the position's required skills found among the
    CV's normalized skills. normalized_position_skills is computed once
    per position by normalize_skills.normalize_position_skills and passed
    in here -- it's candidate-independent, so it must not be recomputed
    (re-querying the taxonomy) inside a per-candidate loop.
    """
    if not normalized_position_skills:
        return 1.0

    cv_canonical_ids = {s.canonical_id for s in normalized_cv_skills if s.canonical_id is not None}
    matched = sum(
        1
        for required in normalized_position_skills
        if required.canonical_id is not None and required.canonical_id in cv_canonical_ids
    )
    return matched / len(normalized_position_skills)


def _sector_score(
    cv: CandidateCV, required_sector_vector: list[float] | None, *, embeddings: Embeddings
) -> float:
    """required_sector_vector is the position's required_sector_experience
    text, embedded once by the caller (candidate-independent) -- only the
    CV's own sector text still needs embedding here, per candidate.
    """
    if required_sector_vector is None:
        return 1.0

    sectors = {experience.sector for experience in cv.experience if experience.sector}
    if not sectors:
        return 0.0

    sector_vectors = embeddings.embed_documents(list(sectors))
    return max(_cosine_similarity(required_sector_vector, vector) for vector in sector_vectors)


def score_soft_criteria(
    cv: CandidateCV,
    normalized_cv_skills: list[NormalizedSkill],
    normalized_position_skills: list[NormalizedSkill],
    required_sector_vector: list[float] | None,
    *,
    embeddings: Embeddings,
) -> tuple[SubScores, float]:
    """ADQ-16. Called for every shortlisted candidate regardless of
    check_hard_filters' outcome, so a hard-filter failure still shows its
    skill/sector fit -- the caller (worker/matching_tasks.py) is
    responsible for discarding the returned compatibility_score (never
    persisting it) when hard filters failed, since that number is a
    ranking signal and a rejected candidate is never ranked (see
    domain/matching.py MatchResult docstring). The SubScores this function
    returns are persisted either way.

    normalized_position_skills/required_sector_vector are computed once
    per position by the caller (app/worker/matching_tasks.py), not once
    per candidate -- see _skill_score/_sector_score docstrings.
    """
    skill_score = _skill_score(normalized_position_skills, normalized_cv_skills)
    sector_score = _sector_score(cv, required_sector_vector, embeddings=embeddings)
    compatibility_score = _SKILL_WEIGHT * skill_score + _SECTOR_WEIGHT * sector_score
    return SubScores(sector_score=sector_score, skill_score=skill_score), compatibility_score


def score(state: PipelineState) -> PipelineState:
    """Graph-node form -- still unwired, same as extract.py's extract(state)
    and normalize_skills.py's normalize_skills(state). check_hard_filters/
    score_soft_criteria above are what the matching worker actually calls.
    """
    raise NotImplementedError

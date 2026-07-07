import math
import re
from collections.abc import Sequence
from datetime import date

from langchain_core.embeddings import Embeddings
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.cv import CandidateCV, NormalizedSkill
from app.domain.matching import SubScores
from app.domain.tdr import ExpertPosition
from app.features.pipeline.nodes.normalize_skills import match_skill_to_taxonomy
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


async def _skill_score(
    position: ExpertPosition,
    normalized_cv_skills: list[NormalizedSkill],
    *,
    session: AsyncSession,
    embeddings: Embeddings,
) -> float:
    if not position.required_skills:
        return 1.0

    cv_canonical_ids = {s.canonical_id for s in normalized_cv_skills if s.canonical_id is not None}
    matched = 0
    for required_term in position.required_skills:
        normalized_requirement = await match_skill_to_taxonomy(
            required_term, session=session, embeddings=embeddings
        )
        if (
            normalized_requirement.canonical_id is not None
            and normalized_requirement.canonical_id in cv_canonical_ids
        ):
            matched += 1
    return matched / len(position.required_skills)


def _sector_score(cv: CandidateCV, position: ExpertPosition, *, embeddings: Embeddings) -> float:
    if not position.required_sector_experience:
        return 1.0

    sectors = {experience.sector for experience in cv.experience if experience.sector}
    if not sectors:
        return 0.0

    required_vector = embeddings.embed_query(position.required_sector_experience)
    sector_vectors = embeddings.embed_documents(list(sectors))
    return max(_cosine_similarity(required_vector, vector) for vector in sector_vectors)


async def score_soft_criteria(
    cv: CandidateCV,
    position: ExpertPosition,
    normalized_cv_skills: list[NormalizedSkill],
    *,
    session: AsyncSession,
    embeddings: Embeddings,
) -> tuple[SubScores, float]:
    """ADQ-16. Only called when check_hard_filters has already passed --
    compatibility_score stays None on a hard-filter failure, never a
    computed number (see domain/matching.py MatchResult docstring).
    """
    skill_score = await _skill_score(
        position, normalized_cv_skills, session=session, embeddings=embeddings
    )
    sector_score = _sector_score(cv, position, embeddings=embeddings)
    compatibility_score = _SKILL_WEIGHT * skill_score + _SECTOR_WEIGHT * sector_score
    return SubScores(sector_score=sector_score, skill_score=skill_score), compatibility_score


def score(state: PipelineState) -> PipelineState:
    """Graph-node form -- still unwired, same as extract.py's extract(state)
    and normalize_skills.py's normalize_skills(state). check_hard_filters/
    score_soft_criteria above are what the matching worker actually calls.
    """
    raise NotImplementedError

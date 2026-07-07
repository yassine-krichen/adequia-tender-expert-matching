"""Live TDR extraction quality regression suite.

Not part of the default `uv run pytest` run (see `addopts` in pyproject.toml)
-- these hit real LLM providers against real documents in docs/tdrs/, which
costs real free-tier quota and real wall-clock time. Run explicitly:

    uv run pytest -m eval

Each fixture in fixtures/*.json is a hand-verified answer key, built by
actually reading the real source document once. Adding a new document:
read its real staffing/expert section once, write a fixture describing
what a correct extraction looks like, then this suite checks every
future retrieval/prompt change against every fixture that came before it
-- no re-reading documents by eye each time.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.common.llm.router import ModelRouter
from app.config.settings import get_settings
from app.domain.tdr import ExpertPosition
from app.features.pipeline.nodes.extract import extract_tdr
from app.features.pipeline.nodes.ingest import extract_raw_text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixtures() -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(_FIXTURES_DIR.glob("*.json"))]


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-·]+", "", text.lower())


def _title_matches(actual_title: str, title_contains_any: list[str]) -> bool:
    normalized_actual = _normalize(actual_title)
    return any(_normalize(candidate) in normalized_actual for candidate in title_contains_any)


def _diploma_matches(actual_diploma: str | None, diploma_contains: str | None) -> bool:
    if diploma_contains is None:
        return True
    if actual_diploma is None:
        return False
    return _normalize(diploma_contains) in _normalize(actual_diploma)


def _find_match(expected: dict[str, Any], actual_positions: list[ExpertPosition]) -> ExpertPosition | None:
    for position in actual_positions:
        if _title_matches(position.position_title, expected["title_contains_any"]) and _diploma_matches(
            position.mandatory_diploma, expected["diploma_contains"]
        ):
            return position
    return None


def _format_report(
    fixture_name: str, expected_positions: list[dict[str, Any]], actual_positions: list[ExpertPosition]
) -> str:
    lines = [f"Extraction mismatch for {fixture_name}", "", "Expected positions:"]
    for expected in expected_positions:
        match = _find_match(expected, actual_positions)
        status = "OK" if match else "MISSING"
        lines.append(
            f"  [{status}] title~{expected['title_contains_any']} "
            f"diploma~{expected['diploma_contains']} years={expected['minimum_years_experience']}"
        )
    lines.append("")
    lines.append("Actual extracted positions:")
    for position in actual_positions:
        lines.append(
            f"  - {position.position_title!r} diploma={position.mandatory_diploma!r} "
            f"years={position.minimum_years_experience!r}"
        )
    return "\n".join(lines)


@pytest.mark.eval
@pytest.mark.parametrize("fixture", _load_fixtures(), ids=lambda f: Path(f["source_file"]).stem)
def test_tdr_extraction_matches_hand_verified_positions(fixture: dict[str, Any]) -> None:
    source_path = _REPO_ROOT / fixture["source_file"]
    raw_text = extract_raw_text(source_path.read_bytes(), source_path.name)

    router = ModelRouter(get_settings())
    tdr = extract_tdr(
        raw_text,
        tdr_id="eval-run",
        source_file_path=source_path.name,
        router=router,
        embeddings=router.get_embedding_model(),
    )

    report = _format_report(source_path.name, fixture["expected_positions"], tdr.positions)
    for expected in fixture["expected_positions"]:
        match = _find_match(expected, tdr.positions)
        assert match is not None, report
        if expected["minimum_years_experience"] is not None:
            assert match.minimum_years_experience == expected["minimum_years_experience"], report

from collections.abc import Sequence
from datetime import date
from typing import Any

import pytest
from langchain_core.embeddings import Embeddings

from app.features.pipeline.nodes.extract import (
    _ExtractedPosition,
    _TDRChunkExtraction,
    _cosine_similarity,
    _merge_chunk_extractions,
    _retrieve_relevant_chunks,
    extract_tdr,
)


class _FakeEmbeddings(Embeddings):
    """1D embeddings where the value itself doubles as a similarity axis —
    makes it trivial to assert which chunks got selected as "relevant".
    """

    def __init__(self, query_vector: list[float], chunk_vectors: dict[str, list[float]]) -> None:
        self._query_vector = query_vector
        self._chunk_vectors = chunk_vectors

    def embed_query(self, text: str) -> list[float]:
        return self._query_vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._chunk_vectors[text] for text in texts]


class _FakeRouter:
    def __init__(self, responses: Sequence[_TDRChunkExtraction | Exception]) -> None:
        self._responses = iter(responses)
        self.call_count = 0

    def invoke_extraction(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _TDRChunkExtraction:
        return self._next_response()

    def invoke_reasoning(
        self, messages: Sequence[Any], structured_output: type[Any] | None = None
    ) -> _TDRChunkExtraction:
        return self._next_response()

    def _next_response(self) -> _TDRChunkExtraction:
        self.call_count += 1
        response = next(self._responses)
        if isinstance(response, Exception):
            raise response
        return response


def _position(title: str) -> _ExtractedPosition:
    return _ExtractedPosition(
        position_title=title, mandatory_diploma="Bac+5", source_span=f"span for {title}"
    )


def test_cosine_similarity_of_identical_vectors_is_one() -> None:
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_of_orthogonal_vectors_is_zero() -> None:
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_retrieve_relevant_chunks_returns_all_chunks_when_below_top_n() -> None:
    chunks = ["a", "b"]
    embeddings = _FakeEmbeddings([1.0], {"a": [1.0], "b": [0.0]})

    assert _retrieve_relevant_chunks(chunks, embeddings, top_n=5) == chunks


def test_retrieve_relevant_chunks_picks_the_closest_to_the_query_vector() -> None:
    chunks = ["irrelevant", "relevant-1", "relevant-2", "also-irrelevant"]
    embeddings = _FakeEmbeddings(
        query_vector=[1.0, 0.0],
        chunk_vectors={
            "irrelevant": [0.0, 1.0],
            "relevant-1": [0.9, 0.1],
            "relevant-2": [1.0, 0.0],
            "also-irrelevant": [0.0, 1.0],
        },
    )

    result = _retrieve_relevant_chunks(chunks, embeddings, top_n=2)

    assert set(result) == {"relevant-1", "relevant-2"}


def test_merge_chunk_extractions_dedupes_positions_by_title_case_insensitive() -> None:
    chunk_1 = _TDRChunkExtraction(mission_title="Mission A", positions=[_position("Team Leader")])
    chunk_2 = _TDRChunkExtraction(positions=[_position("team leader"), _position("QA Expert")])

    merged = _merge_chunk_extractions([chunk_1, chunk_2])

    assert merged.mission_title == "Mission A"
    assert [p.position_title for p in merged.positions] == ["Team Leader", "QA Expert"]


def test_merge_chunk_extractions_combines_fields_of_same_titled_position() -> None:
    """A short TDR often describes one position across several chunks (e.g.
    the position is named in one chunk, its skills bullet list lives in
    another) -- merging must combine both chunks' fields, not silently keep
    only whichever chunk was extracted first.
    """
    chunk_1 = _TDRChunkExtraction(
        positions=[
            _ExtractedPosition(
                position_title="Software Developer",
                source_span="span 1",
                required_skills=["C#"],
            )
        ]
    )
    chunk_2 = _TDRChunkExtraction(
        positions=[
            _ExtractedPosition(
                position_title="software developer",
                mandatory_diploma="Bachelor's degree",
                minimum_years_experience=5.0,
                source_span="span 2",
                required_skills=["ASP.NET", "SQL Server"],
            )
        ]
    )

    merged = _merge_chunk_extractions([chunk_1, chunk_2])

    assert len(merged.positions) == 1
    position = merged.positions[0]
    assert position.required_skills == ["C#", "ASP.NET", "SQL Server"]
    assert position.mandatory_diploma == "Bachelor's degree"
    assert position.minimum_years_experience == 5.0


def test_merge_chunk_extractions_takes_first_non_empty_mission_field() -> None:
    chunk_1 = _TDRChunkExtraction(client=None, sector="Public")
    chunk_2 = _TDRChunkExtraction(client="Ministry", sector="Education")

    merged = _merge_chunk_extractions([chunk_1, chunk_2])

    assert merged.client == "Ministry"
    assert merged.sector == "Public"


def test_extract_tdr_builds_tdr_with_positions_from_retrieved_chunks() -> None:
    router = _FakeRouter(
        [
            _TDRChunkExtraction(
                mission_title="Système de gestion de la scolarité",
                client="Ministère de l'Éducation",
                sector="Éducation",
                deadline="2026-12-01",
                positions=[_position("Chef de projet")],
            )
        ]
    )
    embeddings = _FakeEmbeddings([1.0], {})

    result = extract_tdr(
        "short raw tdr text",
        tdr_id="tdr-1",
        source_file_path="tdr.pdf",
        router=router,
        embeddings=embeddings,
    )

    assert result.tdr_id == "tdr-1"
    assert result.mission_title == "Système de gestion de la scolarité"
    assert result.client == "Ministère de l'Éducation"
    assert result.deadline == date(2026, 12, 1)
    assert len(result.positions) == 1
    assert result.positions[0].position_title == "Chef de projet"
    assert result.positions[0].position_id  # system-assigned, non-empty
    assert router.call_count == 1


def test_extract_tdr_falls_back_to_untitled_mission_when_title_never_found() -> None:
    router = _FakeRouter([_TDRChunkExtraction(positions=[])])
    embeddings = _FakeEmbeddings([1.0], {})

    result = extract_tdr(
        "short raw tdr text",
        tdr_id="tdr-1",
        source_file_path="tdr.pdf",
        router=router,
        embeddings=embeddings,
    )

    assert result.mission_title == "Untitled mission"
    assert result.positions == []

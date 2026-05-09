from src.eval.models import BenchmarkCase, ExpectedSource, RetrievedChunk
from src.eval.persisted_qdrant_retrieval_eval import (
    filter_cases_by_source_paths,
    has_line_overlap,
    required_source_paths,
    score_retrieval_case,
)


def test_score_retrieval_case_matches_primary_source_and_lines() -> None:
    benchmark_case = make_case(
        scoring={"required_source_paths": ["provider/a.md", "provider/b.md"]},
    )
    retrieved_chunks = [
        make_retrieved_chunk("provider/c.md", rank=1, start_line=1, end_line=5),
        make_retrieved_chunk("provider/a.md", rank=2, start_line=10, end_line=20),
        make_retrieved_chunk("provider/b.md", rank=3, start_line=30, end_line=35),
    ]

    metric = score_retrieval_case(
        strategy="strategy-a",
        benchmark_case=benchmark_case,
        retrieved_chunks=retrieved_chunks,
        top_k=5,
    )

    assert metric.primary_hit_at_k == 1.0
    assert metric.primary_rank_at_k == 2
    assert metric.primary_mrr_at_k == 0.5
    assert metric.required_source_recall_at_k == 1.0
    assert metric.line_overlap_recall_at_k == 1.0


def test_score_retrieval_case_respects_top_k() -> None:
    benchmark_case = make_case()
    retrieved_chunks = [
        make_retrieved_chunk("provider/c.md", rank=1, start_line=1, end_line=5),
        make_retrieved_chunk("provider/a.md", rank=2, start_line=10, end_line=20),
    ]

    metric = score_retrieval_case(
        strategy="strategy-a",
        benchmark_case=benchmark_case,
        retrieved_chunks=retrieved_chunks,
        top_k=1,
    )

    assert metric.primary_hit_at_k == 0.0
    assert metric.primary_rank_at_k is None
    assert metric.primary_mrr_at_k == 0.0


def test_required_source_paths_falls_back_to_expected_sources() -> None:
    benchmark_case = make_case(scoring={})

    assert required_source_paths(benchmark_case) == ["provider/a.md"]


def test_has_line_overlap_requires_same_source_path() -> None:
    expected_source = ExpectedSource(
        provider="provider",
        source_path="provider/a.md",
        line_start=10,
        line_end=20,
        evidence_quote="quote",
    )

    assert has_line_overlap(
        expected_source,
        [make_retrieved_chunk("provider/a.md", rank=1, start_line=20, end_line=25)],
    )
    assert not has_line_overlap(
        expected_source,
        [make_retrieved_chunk("provider/b.md", rank=1, start_line=10, end_line=20)],
    )


def test_filter_cases_by_source_paths_uses_primary_source() -> None:
    included = make_case(case_id="included")
    excluded = make_case(case_id="excluded", source_path="provider/b.md")

    assert filter_cases_by_source_paths(
        [included, excluded],
        {"provider/a.md"},
    ) == [included]


def make_case(
    case_id: str = "case-1",
    source_path: str = "provider/a.md",
    scoring: dict[str, object] | None = None,
) -> BenchmarkCase:
    return BenchmarkCase(
        case_id=case_id,
        question="Question?",
        gold_answer="Answer.",
        case_type="single_source_answer",
        task_type="retrieval",
        risk_level="low",
        expected_behavior="Return evidence.",
        expected_sources=(
            ExpectedSource(
                provider="provider",
                source_path=source_path,
                line_start=10,
                line_end=20,
                evidence_quote="quote",
                relationship="primary",
            ),
        ),
        scoring=scoring or {"required_source_paths": [source_path]},
    )


def make_retrieved_chunk(
    source_path: str,
    rank: int,
    start_line: int,
    end_line: int,
) -> RetrievedChunk:
    return RetrievedChunk(
        case_id="case-1",
        strategy="strategy-a",
        rank=rank,
        score=1.0 / rank,
        chunk_id=f"chunk-{rank}",
        source_path=source_path,
        provider="provider",
        text="text",
        start_line=start_line,
        end_line=end_line,
    )

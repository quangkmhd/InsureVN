from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "05_training_eval"
    / "run_answer_citation_eval.py"
)
SPEC = importlib.util.spec_from_file_location("run_answer_citation_eval", MODULE_PATH)
answer_eval = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["run_answer_citation_eval"] = answer_eval
SPEC.loader.exec_module(answer_eval)


def make_case() -> answer_eval.AnswerBenchmarkCase:
    return answer_eval.AnswerBenchmarkCase(
        case_id="case-1",
        benchmark_file="benchmark.jsonl",
        benchmark_version="v1",
        query="PTI chi trả giới hạn nào?",
        expected_answer="PTI chi trả tối đa 100.000.000 đồng cho điều trị nội trú.",
        source_path="pti.com.vn/policy.md",
        source_line=12,
        provider="pti.com.vn",
        difficulty="medium",
        task_type="coverage_qa",
        evidence_quote="",
        expected_evidence=("100.000.000", "điều trị nội trú"),
        must_cite_source=True,
        risk="medium",
    )


def make_context() -> answer_eval.RetrievedContext:
    return answer_eval.RetrievedContext(
        citation_id="S1",
        rank=1,
        source_path="pti.com.vn/policy.md",
        document_id="pti_policy",
        document_name="PTI Policy",
        section_heading="Quyền lợi nội trú",
        text="PTI chi trả tối đa 100.000.000 đồng cho điều trị nội trú.",
        source_match=True,
        quote_match=True,
        score=0.9,
    )


def test_evaluate_generated_answer_rewards_grounded_cited_answer() -> None:
    result = answer_eval.evaluate_generated_answer(
        case=make_case(),
        scenario_name="hybrid_company_filter_rerank",
        contexts=[make_context()],
        answer="PTI chi trả tối đa 100.000.000 đồng cho điều trị nội trú. [S1]",
        generation_mode="extractive",
        generation_status="completed",
        generation_latency_ms=1.0,
        generation_error="",
        threshold=0.65,
    )

    assert result.expected_source_in_context is True
    assert result.expected_source_cited is True
    assert result.answer_has_citation is True
    assert result.valid_citation_rate == 1.0
    assert result.numeric_claim_support == 1.0
    assert result.success is True


def test_citation_coverage_attaches_detached_trailing_citation() -> None:
    answer = "PTI chi trả tối đa 100.000.000 đồng cho điều trị nội trú. [S1]"

    assert answer_eval.calculate_citation_coverage(answer) == 1.0


def test_extractive_answer_cites_each_statement() -> None:
    context = answer_eval.RetrievedContext(
        citation_id="S1",
        rank=1,
        source_path="pti.com.vn/policy.md",
        document_id="pti_policy",
        document_name="PTI Policy",
        section_heading="Quyền lợi nội trú",
        text=(
            "PTI chi trả tối đa 100.000.000 đồng. "
            "Thời hạn giải quyết là 15 ngày làm việc."
        ),
        source_match=True,
        quote_match=True,
        score=0.9,
    )

    answer = answer_eval.build_extractive_answer(contexts=[context])

    assert answer.count("[S1]") == 2
    assert "100.000.000 đồng [S1]." in answer
    assert ". [S1]" not in answer
    assert answer_eval.calculate_citation_coverage(answer) == 1.0


def test_invalid_citation_id_cannot_succeed() -> None:
    result = answer_eval.evaluate_generated_answer(
        case=make_case(),
        scenario_name="hybrid_company_filter_rerank",
        contexts=[make_context()],
        answer="PTI chi trả tối đa 100.000.000 đồng cho điều trị nội trú [S99].",
        generation_mode="extractive",
        generation_status="completed",
        generation_latency_ms=1.0,
        generation_error="",
        threshold=0.65,
    )

    assert result.expected_source_cited is False
    assert result.valid_citation_rate == 0.0
    assert result.citation_coverage == 0.0
    assert result.success is False


def test_numeric_support_uses_cited_context_not_any_retrieved_context() -> None:
    uncited_context = answer_eval.RetrievedContext(
        citation_id="S2",
        rank=2,
        source_path="pti.com.vn/other.md",
        document_id="pti_other",
        document_name="PTI Other",
        section_heading="Thời hạn",
        text="Thời hạn giải quyết là 15 ngày làm việc.",
        source_match=False,
        quote_match=False,
        score=0.6,
    )

    result = answer_eval.evaluate_generated_answer(
        case=make_case(),
        scenario_name="hybrid_company_filter_rerank",
        contexts=[make_context(), uncited_context],
        answer="PTI chi trả tối đa 15 ngày làm việc [S1].",
        generation_mode="extractive",
        generation_status="completed",
        generation_latency_ms=1.0,
        generation_error="",
        threshold=0.65,
    )

    assert result.unsupported_numeric_claim_count == 1
    assert result.numeric_claim_support == 0.0


def test_evaluate_generated_answer_penalizes_wrong_source_and_number() -> None:
    result = answer_eval.evaluate_generated_answer(
        case=make_case(),
        scenario_name="hybrid_company_filter_rerank",
        contexts=[make_context()],
        answer="PTI chi trả tối đa 999.000.000 đồng cho điều trị nội trú. [S2]",
        generation_mode="extractive",
        generation_status="completed",
        generation_latency_ms=1.0,
        generation_error="",
        threshold=0.65,
    )

    assert result.expected_source_cited is False
    assert result.valid_citation_rate == 0.0
    assert result.unsupported_numeric_claim_count == 1
    assert result.numeric_claim_support == 0.0
    assert result.success is False


def test_load_retrieval_contexts_filters_scenario(tmp_path: Path) -> None:
    retrieval_dir = tmp_path / "run"
    retrieval_dir.mkdir()
    rows = [
        {
            "case_id": "case-1",
            "scenario_name": "hybrid_company_filter_rerank",
            "rank": 2,
            "source_path": "pti.com.vn/second.md",
            "content_preview": "second",
        },
        {
            "case_id": "case-1",
            "scenario_name": "hybrid_company_filter_rerank",
            "rank": 1,
            "source_path": "pti.com.vn/first.md",
            "content_preview": "first",
        },
        {
            "case_id": "case-1",
            "scenario_name": "hybrid",
            "rank": 1,
            "source_path": "wrong.md",
            "content_preview": "wrong",
        },
    ]
    retrieval_path = retrieval_dir / "retrievals.jsonl"
    retrieval_path.write_text(
        "\n".join(answer_eval.json.dumps(row, ensure_ascii=False) for row in rows)
        + "\n",
        encoding="utf-8",
    )

    contexts_by_case = answer_eval.load_retrieval_contexts(
        retrieval_eval_dir=retrieval_dir,
        scenario="hybrid_company_filter_rerank",
        top_contexts=1,
    )

    assert list(contexts_by_case) == ["case-1"]
    assert len(contexts_by_case["case-1"]) == 1
    assert contexts_by_case["case-1"][0].citation_id == "S1"
    assert contexts_by_case["case-1"][0].source_path == "pti.com.vn/first.md"


def test_write_outputs_creates_manifest_file(tmp_path: Path) -> None:
    result = answer_eval.evaluate_generated_answer(
        case=make_case(),
        scenario_name="hybrid_company_filter_rerank",
        contexts=[make_context()],
        answer="PTI chi trả tối đa 100.000.000 đồng cho điều trị nội trú. [S1]",
        generation_mode="extractive",
        generation_status="completed",
        generation_latency_ms=1.0,
        generation_error="",
        threshold=0.65,
    )
    config = answer_eval.AnswerEvalConfig(
        retrieval_eval_dir=tmp_path / "retrieval",
        benchmark_dir=tmp_path / "benchmark",
        output_dir=tmp_path / "output",
        generation_mode="extractive",
        provider_slots=(),
        gemini_api_keys=(),
    )
    config.output_dir.mkdir()

    answer_eval.write_outputs(config, [result])

    assert (config.output_dir / "manifest.json").exists()
    assert not (config.output_dir / "manifest.json" / "manifest.json").exists()

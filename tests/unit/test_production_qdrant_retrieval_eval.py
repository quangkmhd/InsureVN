import importlib.util
import sys
from pathlib import Path
from typing import Any

from src.models.evidence import Evidence, RetrievalMode, SourceType

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "05_training_eval"
    / "run_production_qdrant_retrieval_eval.py"
)
SPEC = importlib.util.spec_from_file_location(
    "production_qdrant_retrieval_eval",
    SCRIPT_PATH,
)
assert SPEC is not None
eval_runner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = eval_runner
SPEC.loader.exec_module(eval_runner)


class FakeRetriever:
    def __init__(self, evidences: list[Evidence]) -> None:
        self.evidences = evidences
        self.received_top_k: int | None = None

    def retrieve(self, plan: Any) -> list[Evidence]:
        self.received_top_k = plan.top_k
        return list(self.evidences)


class FakeReranker:
    def __init__(self, expected_source_path: str) -> None:
        self.expected_source_path = expected_source_path
        self.received_candidate_count: int | None = None
        self.received_top_k: int | None = None

    def rerank_evidence(
        self,
        *,
        query: str,
        evidence_items: list[Evidence],
        top_k: int | None = None,
    ) -> list[Evidence]:
        del query
        self.received_candidate_count = len(evidence_items)
        self.received_top_k = top_k
        expected = next(
            evidence
            for evidence in evidence_items
            if evidence.metadata["source_path"] == self.expected_source_path
        )
        remaining = [
            evidence for evidence in evidence_items if evidence is not expected
        ]
        return ([expected] + remaining)[: top_k or len(evidence_items)]


def test_rerank_scenario_records_pre_and_post_rerank_metrics() -> None:
    expected_source_path = "pti.com.vn/policy/expected.md"
    evidences = [
        Evidence(
            source_type=SourceType.QDRANT_CHUNK,
            source_id=f"chunk-{index}",
            content=f"candidate {index}",
            metadata={
                "source_path": expected_source_path
                if index == 12
                else f"pti.com.vn/policy/other-{index}.md",
                "fusion_score": 1.0 - (index / 100.0),
            },
            confidence=0.5,
            retrieved_by="QdrantRetriever",
        )
        for index in range(1, 31)
    ]
    retriever = FakeRetriever(evidences=evidences)
    reranker = FakeReranker(expected_source_path=expected_source_path)
    case = eval_runner.BenchmarkCase(
        case_id="case-1",
        benchmark_file="bench.jsonl",
        benchmark_version="bench",
        query="expected clause?",
        source_path=expected_source_path,
        provider="pti.com.vn",
        difficulty=None,
        task_type=None,
        evidence_quote=None,
        expected_evidence=(),
        raw={},
    )
    scenario = eval_runner.EvalScenario(
        name="hybrid_rerank",
        retrieval_mode=RetrievalMode.HYBRID,
        use_reranker=True,
    )

    case_metrics, retrieval_rows = eval_runner.evaluate_case(
        retriever=retriever,
        case=case,
        scenario=scenario,
        top_k=10,
        retrieve_top_k=30,
        rerank_top_k=10,
        reranker=reranker,
    )

    assert retriever.received_top_k == 30
    assert reranker.received_candidate_count == 30
    assert reranker.received_top_k == 10
    assert case_metrics["candidate_retrieved_count"] == 30
    assert case_metrics["retrieved_count"] == 10
    assert case_metrics["pre_rerank_source_rank"] == 12
    assert case_metrics["pre_rerank_source_hit_at_10"] == 0
    assert case_metrics["source_rank"] == 1
    assert case_metrics["source_hit_at_10"] == 1
    assert case_metrics["source_rank_delta_after_rerank"] == -11
    assert [row["stage"] for row in retrieval_rows].count("pre_rerank") == 30
    assert [row["stage"] for row in retrieval_rows].count("final") == 10

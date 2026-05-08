"""DeepEval-backed retrieval evaluation."""

from __future__ import annotations

from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
)
from deepeval.test_case import LLMTestCase

from src.eval.models import BenchmarkCase, MetricScore, RetrievedChunk


class DeepEvalRetrievalEvaluator:
    """Evaluate retrieved contexts with DeepEval's built-in RAG metrics."""

    def __init__(
        self,
        threshold: float,
        model: str | None = None,
        include_reason: bool = False,
    ) -> None:
        self.threshold = threshold
        self.model = model
        self.include_reason = include_reason
        self.metrics = [
            ContextualPrecisionMetric(
                threshold=threshold,
                model=model,
                include_reason=include_reason,
                async_mode=False,
            ),
            ContextualRecallMetric(
                threshold=threshold,
                model=model,
                include_reason=include_reason,
                async_mode=False,
            ),
            ContextualRelevancyMetric(
                threshold=threshold,
                model=model,
                include_reason=include_reason,
                async_mode=False,
            ),
        ]

    @property
    def metric_names(self) -> list[str]:
        """Return metric class names used by this evaluator."""

        return [metric.__class__.__name__ for metric in self.metrics]

    def cache_config_payload(self) -> dict[str, object]:
        """Return scoring settings that affect metric values."""

        return {
            "threshold": self.threshold,
            "model": self.model,
            "include_reason": self.include_reason,
            "metric_names": self.metric_names,
        }

    def evaluate_case(
        self,
        strategy: str,
        benchmark_case: BenchmarkCase,
        retrieved_chunks: list[RetrievedChunk],
        scoring_cache_key: str | None = None,
    ) -> list[MetricScore]:
        """Evaluate one query's retrieval context."""

        test_case = LLMTestCase(
            input=benchmark_case.question,
            expected_output=benchmark_case.gold_answer,
            retrieval_context=[chunk.text for chunk in retrieved_chunks],
        )
        scores: list[MetricScore] = []
        for metric in self.metrics:
            try:
                score = metric.measure(
                    test_case,
                    _show_indicator=False,
                    _log_metric_to_confident=False,
                )
                success = bool(getattr(metric, "success", score >= self.threshold))
                reason = getattr(metric, "reason", None)
                scores.append(
                    MetricScore(
                        case_id=benchmark_case.case_id,
                        strategy=strategy,
                        metric_name=metric.__class__.__name__,
                        score=float(score),
                        threshold=self.threshold,
                        success=success,
                        reason=reason,
                        scoring_cache_key=scoring_cache_key,
                    )
                )
            except Exception as exc:
                scores.append(
                    MetricScore(
                        case_id=benchmark_case.case_id,
                        strategy=strategy,
                        metric_name=metric.__class__.__name__,
                        score=None,
                        threshold=self.threshold,
                        success=None,
                        error=f"{type(exc).__name__}: {exc}",
                        scoring_cache_key=scoring_cache_key,
                    )
                )
        return scores

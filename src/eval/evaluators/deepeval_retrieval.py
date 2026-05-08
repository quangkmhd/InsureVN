"""DeepEval-backed retrieval evaluation."""

from __future__ import annotations

import json
import re
from typing import Any

from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
)
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase
from llama_index.core.llms import LLM
from pydantic import BaseModel

from src.eval.models import BenchmarkCase, MetricScore, RetrievedChunk

JSON_CODE_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class ProviderPoolDeepEvalLLM(DeepEvalBaseLLM):
    """DeepEval model adapter backed by the configured provider pool."""

    def __init__(self, provider_pool_llm: LLM, model_name: str) -> None:
        self.provider_pool_llm = provider_pool_llm
        super().__init__(model=model_name)

    def load_model(self, *_args: object, **_kwargs: object) -> LLM:
        """Return the configured provider-pool LLM."""

        return self.provider_pool_llm

    def generate(
        self,
        prompt: str,
        schema: type[BaseModel] | None = None,
        **_: object,
    ) -> str | BaseModel:
        """Generate text or a Pydantic schema instance for DeepEval metrics."""

        if schema is None:
            return self._complete(prompt)

        schema_prompt = build_schema_prompt(prompt, schema)
        response_text = self._complete(schema_prompt)
        try:
            return parse_schema_response(response_text, schema)
        except ValueError:
            retry_text = self._complete(build_json_retry_prompt(schema_prompt))
            return parse_schema_response(retry_text, schema)

    async def a_generate(
        self,
        prompt: str,
        schema: type[BaseModel] | None = None,
        **kwargs: object,
    ) -> str | BaseModel:
        """Run sync generation from DeepEval's async interface."""

        return self.generate(prompt, schema=schema, **kwargs)

    def get_model_name(self, *_args: object, **_kwargs: object) -> str:
        """Return a stable model name for reports and cache keys."""

        return self.name

    def supports_structured_outputs(self) -> bool:
        """Declare schema support through JSON parsing."""

        return True

    def supports_json_mode(self) -> bool:
        """Declare JSON-mode support through prompt constraints."""

        return True

    def _complete(self, prompt: str) -> str:
        """Call the underlying LlamaIndex LLM and return plain text."""

        return str(self.model.complete(prompt)).strip()


class DeepEvalRetrievalEvaluator:
    """Evaluate retrieved contexts with DeepEval's built-in RAG metrics."""

    def __init__(
        self,
        threshold: float,
        model: str | DeepEvalBaseLLM | None = None,
        include_reason: bool = False,
    ) -> None:
        self.threshold = threshold
        self.model = model
        self.model_name = model_name_for_cache(model)
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
            "model": self.model_name,
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


def build_schema_prompt(prompt: str, schema: type[BaseModel]) -> str:
    """Append a strict JSON instruction for DeepEval structured outputs."""

    return (
        f"{prompt}\n\n"
        "Return only valid JSON. Do not include markdown fences, explanation, "
        "or text outside the JSON object. The JSON must match this schema:\n"
        f"{json.dumps(schema_json_schema(schema), ensure_ascii=False)}"
    )


def build_json_retry_prompt(prompt: str) -> str:
    """Build a stricter retry prompt for invalid JSON responses."""

    return (
        f"{prompt}\n\n"
        "Your previous response was not valid JSON for the requested schema. "
        "Return only the JSON object now."
    )


def parse_schema_response(
    response_text: str,
    schema: type[BaseModel],
) -> BaseModel:
    """Parse a provider-pool response into the requested Pydantic schema."""

    json_text = extract_json_text(response_text)
    try:
        if hasattr(schema, "model_validate_json"):
            return schema.model_validate_json(json_text)
        return schema.parse_raw(json_text)
    except Exception as exc:
        preview = response_text[:500].replace("\n", " ")
        msg = f"Provider-pool judge did not return schema-valid JSON: {preview}"
        raise ValueError(msg) from exc


def extract_json_text(response_text: str) -> str:
    """Extract the first JSON object or array from an LLM response."""

    stripped = response_text.strip()
    if is_valid_json(stripped):
        return stripped

    code_block_match = JSON_CODE_BLOCK_PATTERN.search(stripped)
    if code_block_match is not None:
        candidate = code_block_match.group(1).strip()
        if is_valid_json(candidate):
            return candidate

    for start_index, character in enumerate(stripped):
        if character not in "{[":
            continue
        candidate = balanced_json_candidate(stripped[start_index:])
        if candidate and is_valid_json(candidate):
            return candidate

    msg = "No valid JSON object or array found in provider-pool judge response."
    raise ValueError(msg)


def balanced_json_candidate(text: str) -> str:
    """Return the first balanced JSON-looking object or array prefix."""

    opening = text[0]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escaped = False
    for index, character in enumerate(text):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return text[: index + 1]
    return ""


def is_valid_json(text: str) -> bool:
    """Return True if text is valid JSON."""

    try:
        json.loads(text)
    except json.JSONDecodeError:
        return False
    return True


def schema_json_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """Return a Pydantic schema across v1/v2."""

    if hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()
    return schema.schema()


def model_name_for_cache(model: str | DeepEvalBaseLLM | None) -> str:
    """Return a stable judge model name for manifests and cache keys."""

    if model is None:
        return "deepeval-default"
    if isinstance(model, str):
        return model
    return model.get_model_name()

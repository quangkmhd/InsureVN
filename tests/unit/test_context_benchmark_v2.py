import json

import pytest

from src.eval.context_benchmark_v2 import (
    CaseGenerationError,
    ContextChunk,
    build_case_candidates,
    case_passes_quality_caps,
    chunk_document_text,
    generate_case_for_candidate,
    normalize_case_risk_level,
    oversampled_distribution,
    verify_benchmark_output,
)
from src.eval.llm_provider_slots import EvalLLMProviderSlot


def test_chunk_document_text_tracks_line_ranges_and_tables() -> None:
    text = "a b c d e\n| A | B |\n|---|---|\n| 1 | 2 |\nf g h i j\n"

    chunks = chunk_document_text(
        provider="provider",
        source_path="provider/doc.md",
        text=text,
        target_tokens=5,
        min_tokens=1,
    )

    assert chunks[0].start_line == 1
    assert chunks[0].end_line >= 1
    assert any(chunk.contains_table for chunk in chunks)
    assert all(chunk.token_count > 0 for chunk in chunks)


def test_chunk_document_text_trims_blank_lines_without_shifting_line_ranges() -> None:
    text = "\n\nQuyền lợi A được chi trả.\n\n"

    chunks = chunk_document_text(
        provider="provider",
        source_path="provider/doc.md",
        text=text,
        target_tokens=5,
        min_tokens=1,
    )

    assert chunks[0].text == "Quyền lợi A được chi trả."
    assert chunks[0].start_line == 3
    assert chunks[0].end_line == 3


def test_build_case_candidates_respects_distribution() -> None:
    chunks = make_chunks(non_table_count=12, table_count=3)

    candidates = build_case_candidates(
        chunks,
        distribution={
            "single_context": 3,
            "two_context": 3,
            "three_context": 3,
            "table_context": 1,
        },
        random_seed=7,
    )

    case_types = [candidate.case_type for candidate in candidates]
    assert case_types.count("single_context") == 3
    assert case_types.count("two_context") == 3
    assert case_types.count("three_context") == 3
    assert case_types.count("table_context") == 1
    assert all(
        any(chunk.contains_table for chunk in candidate.contexts)
        for candidate in candidates
        if candidate.case_type == "table_context"
    )


def test_build_case_candidates_prefers_same_source_for_multi_context() -> None:
    chunks = [
        ContextChunk(
            chunk_id=f"same-{index}",
            provider="provider",
            source_path="provider/same.md",
            text=f"Nội dung {index}",
            start_line=index + 1,
            end_line=index + 1,
            token_count=3,
            contains_table=False,
        )
        for index in range(3)
    ]
    chunks.append(
        ContextChunk(
            chunk_id="other-1",
            provider="provider",
            source_path="provider/other.md",
            text="Nội dung khác",
            start_line=1,
            end_line=1,
            token_count=3,
            contains_table=False,
        )
    )

    candidates = build_case_candidates(
        chunks,
        distribution={"three_context": 1},
        random_seed=2,
    )

    assert {chunk.source_path for chunk in candidates[0].contexts} == {
        "provider/same.md"
    }


def test_oversampled_distribution_keeps_workers_busy_for_small_top_up() -> None:
    distribution = oversampled_distribution({"three_context": 1}, worker_count=21)

    assert distribution == {"three_context": 21}


def test_generate_case_retries_twice_then_accepts_valid_payload() -> None:
    attempts = 0

    def fake_call(
        _slot: EvalLLMProviderSlot,
        _prompt: str,
        _timeout_seconds: float,
    ) -> dict[str, object]:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary")
        return {
            "question": "Quyền lợi được nêu thế nào?",
            "gold_answer": "Quyền lợi A được chi trả.",
            "evidence_quotes": [
                {
                    "chunk_id": "chunk-1",
                    "quote": "Quyền lợi A được chi trả.",
                }
            ],
            "task_type": "coverage",
            "risk_level": "medium",
        }

    case = generate_case_for_candidate(
        candidate=make_candidate(),
        case_index=1,
        slot=make_slot(),
        call_llm=fake_call,
        timeout_seconds=1,
        max_retries=2,
    )

    assert attempts == 3
    assert case["id"] == "hrag_ctx_v2_00001"
    assert case["expected_sources"][0]["evidence_quote"] == (
        "Quyền lợi A được chi trả."
    )


def test_generate_case_fails_after_two_retries() -> None:
    def fake_call(
        _slot: EvalLLMProviderSlot,
        _prompt: str,
        _timeout_seconds: float,
    ) -> dict[str, object]:
        raise RuntimeError("temporary")

    with pytest.raises(CaseGenerationError):
        generate_case_for_candidate(
            candidate=make_candidate(),
            case_index=1,
            slot=make_slot(),
            call_llm=fake_call,
            timeout_seconds=1,
            max_retries=2,
        )


def test_generate_case_snaps_near_quote_to_context_text() -> None:
    def fake_call(
        _slot: EvalLLMProviderSlot,
        _prompt: str,
        _timeout_seconds: float,
    ) -> dict[str, object]:
        return {
            "question": "Quyền lợi A được nêu thế nào?",
            "gold_answer": "Quyền lợi A được chi trả theo hợp đồng.",
            "evidence_quotes": [
                {
                    "chunk_id": "chunk-1",
                    "quote": "Quyền lợi A chi trả theo hợp đồng",
                }
            ],
            "task_type": "coverage",
            "risk_level": "medium",
        }

    case = generate_case_for_candidate(
        candidate=make_candidate(
            text="Quyền lợi A được chi trả theo hợp đồng."
        ),
        case_index=1,
        slot=make_slot(),
        call_llm=fake_call,
        timeout_seconds=1,
        max_retries=0,
    )

    assert case["expected_sources"][0]["evidence_quote"] == (
        "Quyền lợi A được chi trả theo hợp đồng."
    )


def test_generate_case_groups_quotes_by_context_with_exact_quote_lines() -> None:
    def fake_call(
        _slot: EvalLLMProviderSlot,
        _prompt: str,
        _timeout_seconds: float,
    ) -> dict[str, object]:
        return {
            "question": "Quyền lợi và loại trừ được nêu thế nào?",
            "gold_answer": "Quyền lợi A được chi trả nhưng loại trừ B.",
            "evidence_quotes": [
                {"chunk_id": "chunk-1", "quote": "Quyền lợi A được chi trả."},
                {"chunk_id": "chunk-1", "quote": "Loại trừ B không được chi trả."},
            ],
            "task_type": "exclusion",
            "risk_level": "medium",
        }

    case = generate_case_for_candidate(
        candidate=make_candidate(
            text=(
                "Dòng mở đầu.\n"
                "Quyền lợi A được chi trả.\n"
                "Loại trừ B không được chi trả.\n"
            )
        ),
        case_index=1,
        slot=make_slot(),
        call_llm=fake_call,
        timeout_seconds=1,
        max_retries=0,
    )

    assert len(case["expected_sources"]) == 1
    source = case["expected_sources"][0]
    assert source["line_start"] == 2
    assert source["line_end"] == 3
    assert [quote["evidence_quote"] for quote in source["evidence_quotes"]] == [
        "Quyền lợi A được chi trả.",
        "Loại trừ B không được chi trả.",
    ]
    assert case["risk_level"] == "high"


def test_case_quality_caps_reject_provider_list_and_hotline_after_limit() -> None:
    case = {
        "task_type": "provider_list",
        "question": "Liên hệ hotline nào để được hỗ trợ?",
        "gold_answer": "Liên hệ hotline 1900 để được hỗ trợ.",
    }
    accepted_cases = [
        {
            "task_type": "provider_list",
            "question": f"Hotline {index}?",
            "gold_answer": "Liên hệ hotline 1900.",
        }
        for index in range(15)
    ]

    assert not case_passes_quality_caps(case, accepted_cases)


def test_normalize_case_risk_level_marks_claim_and_exclusion_high() -> None:
    assert normalize_case_risk_level("claim", "medium") == "high"
    assert normalize_case_risk_level("exclusion", "low") == "high"
    assert normalize_case_risk_level("provider_list", "low") == "low"


def test_verify_benchmark_output_rejects_quote_outside_source_lines(
    tmp_path,
) -> None:
    input_dir = tmp_path / "corpus"
    source_path = input_dir / "provider" / "doc.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("\nQuyền lợi A được chi trả.\n", encoding="utf-8")

    output_dir = tmp_path / "benchmark"
    output_dir.mkdir()
    case = {
        "id": "hrag_ctx_v2_00001",
        "case_type": "single_context",
        "question": "Quyền lợi A thế nào?",
        "gold_answer": "Quyền lợi A được chi trả.",
        "expected_sources": [
            {
                "source_path": "provider/doc.md",
                "chunk_id": "chunk-1",
                "line_start": 1,
                "line_end": 1,
                "contains_table": False,
                "evidence_quote": "Quyền lợi A được chi trả.",
                "evidence_quotes": [
                    {
                        "evidence_quote": "Quyền lợi A được chi trả.",
                        "line_start": 1,
                        "line_end": 1,
                    }
                ],
            }
        ],
        "source_constraints": {
            "context_count": 1,
            "required_chunk_ids": ["chunk-1"],
            "must_include_table_evidence": False,
        },
    }
    (output_dir / "health_rag_context_benchmark_v2.jsonl").write_text(
        json.dumps(case, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="quote not found"):
        verify_benchmark_output(
            output_dir,
            expected_distribution={"single_context": 1},
            input_dir=input_dir,
        )


def make_candidate(text: str = "Quyền lợi A được chi trả."):
    return build_case_candidates(
        [
            ContextChunk(
                chunk_id="chunk-1",
                provider="provider",
                source_path="provider/doc.md",
                text=text,
                start_line=1,
                end_line=1,
                token_count=5,
                contains_table=False,
            )
        ],
        distribution={"single_context": 1},
        random_seed=1,
    )[0]


def make_slot() -> EvalLLMProviderSlot:
    return EvalLLMProviderSlot(
        slot_id="slot-1",
        provider="openrouter",
        model="model-a",
        api_key="key-a",
        base_url="https://openrouter.ai/api/v1/chat/completions",
    )


def make_chunks(non_table_count: int, table_count: int) -> list[ContextChunk]:
    chunks: list[ContextChunk] = []
    for index in range(non_table_count):
        chunks.append(
            ContextChunk(
                chunk_id=f"text-{index}",
                provider="provider",
                source_path=f"provider/text-{index}.md",
                text=f"Quyền lợi {index} được chi trả.",
                start_line=1,
                end_line=2,
                token_count=6,
                contains_table=False,
            )
        )
    for index in range(table_count):
        chunks.append(
            ContextChunk(
                chunk_id=f"table-{index}",
                provider="provider",
                source_path=f"provider/table-{index}.md",
                text="| A | B |\n|---|---|\n| 1 | 2 |",
                start_line=1,
                end_line=3,
                token_count=9,
                contains_table=True,
            )
        )
    return chunks

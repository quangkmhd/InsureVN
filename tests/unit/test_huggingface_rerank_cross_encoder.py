from src.services.document_retrieval.huggingface_rerank_cross_encoder import (
    HuggingFaceRerankCrossEncoder,
)


class FakeCrossEncoder:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def rank(self, **kwargs):
        self.calls.append(kwargs)
        query = str(kwargs["query"])
        documents = list(kwargs["documents"])
        if query == "hạn mức nội trú?":
            return [
                {"corpus_id": 1, "score": 0.91},
                {"corpus_id": 0, "score": 0.12},
            ]
        return [
            {"corpus_id": index, "score": float(index) / 10.0}
            for index, _document in enumerate(documents)
        ]


def test_huggingface_rerank_cross_encoder_maps_rank_scores_to_input_order() -> None:
    fake_model = FakeCrossEncoder()
    cross_encoder = HuggingFaceRerankCrossEncoder(
        model_name="Qwen/Qwen3-Reranker-0.6B",
        batch_size=4,
        max_length=1024,
        trust_remote_code=True,
        cross_encoder_model=fake_model,
    )

    scores = cross_encoder.score(
        [
            ("hạn mức nội trú?", "unrelated"),
            ("hạn mức nội trú?", "limit_amount: 100000000"),
        ]
    )

    assert scores == [0.12, 0.91]
    assert fake_model.calls == [
        {
            "query": "hạn mức nội trú?",
            "documents": ["unrelated", "limit_amount: 100000000"],
            "top_k": 2,
            "return_documents": False,
            "batch_size": 4,
            "show_progress_bar": False,
            "convert_to_numpy": True,
            "device": None,
        }
    ]


def test_huggingface_rerank_cross_encoder_groups_pairs_by_query() -> None:
    fake_model = FakeCrossEncoder()
    cross_encoder = HuggingFaceRerankCrossEncoder(
        model_name="BAAI/bge-reranker-v2-m3",
        batch_size=2,
        cross_encoder_model=fake_model,
    )

    scores = cross_encoder.score(
        [
            ("q1", "d1"),
            ("q2", "d2"),
            ("q2", "d3"),
        ]
    )

    assert scores == [0.0, 0.0, 0.1]
    assert len(fake_model.calls) == 2


def test_huggingface_rerank_cross_encoder_requires_model_name() -> None:
    try:
        HuggingFaceRerankCrossEncoder(model_name="")
    except ValueError as exc:
        assert "model_name" in str(exc)
    else:
        raise AssertionError("Expected model_name validation to fail.")

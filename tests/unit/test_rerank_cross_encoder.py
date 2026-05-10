import torch

from src.services.document_retrieval import rerank_cross_encoder


def test_build_rerank_cross_encoder_uses_local_huggingface_adapter(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeHuggingFaceRerankCrossEncoder:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        rerank_cross_encoder,
        "HuggingFaceRerankCrossEncoder",
        FakeHuggingFaceRerankCrossEncoder,
    )

    provider = rerank_cross_encoder.build_rerank_cross_encoder(
        provider="HUGGINGFACE",
        model_name="Qwen/Qwen3-Reranker-0.6B",
        batch_size=6,
        max_length=2048,
        device="cuda",
        trust_remote_code=True,
        backend="torch",
        load_in_4bit=True,
        device_map="auto",
        attn_implementation="flash_attention_2",
        torch_dtype_name="float16",
    )

    assert isinstance(provider, FakeHuggingFaceRerankCrossEncoder)
    assert captured == {
        "model_name": "Qwen/Qwen3-Reranker-0.6B",
        "batch_size": 6,
        "max_length": 2048,
        "device": "cuda",
        "trust_remote_code": True,
        "backend": "torch",
        "model_kwargs": {
            "load_in_4bit": True,
            "device_map": "auto",
            "attn_implementation": "flash_attention_2",
            "torch_dtype": torch.float16,
        },
    }


def test_build_rerank_cross_encoder_rejects_unknown_provider() -> None:
    try:
        rerank_cross_encoder.build_rerank_cross_encoder(
            provider="jina",
            model_name="model",
        )
    except ValueError as exc:
        assert "Unsupported RAG_RERANK_PROVIDER" in str(exc)
    else:
        raise AssertionError("Unsupported rerank provider must raise.")

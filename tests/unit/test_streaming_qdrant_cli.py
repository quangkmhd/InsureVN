import importlib.util
from pathlib import Path


def test_streaming_cli_parses_benchmark_and_corpus_paths() -> None:
    module = load_streaming_cli_module()

    args = module.parse_args(
        [
            "--benchmark-path",
            "data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl",
            "--corpus-dir",
            "data/health_insurance/health_insurance_markdowns_interpreted_cleaned",
        ]
    )

    assert args.benchmark_path == Path(
        "data/benchmark/health_rag_context_benchmark_v2/health_rag_context_benchmark_v2.jsonl"
    )
    assert args.corpus_dir == Path(
        "data/health_insurance/health_insurance_markdowns_interpreted_cleaned"
    )


def load_streaming_cli_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "05_training_eval"
        / "run_streaming_chunking_embedding_qdrant.py"
    )
    spec = importlib.util.spec_from_file_location(
        "run_streaming_chunking_embedding_qdrant",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

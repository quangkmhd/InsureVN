import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_safe_eval_script() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "05_training_eval"
        / "run_safe_chunking_eval.py"
    )
    spec = importlib.util.spec_from_file_location(
        "run_safe_chunking_eval",
        script_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_safe_eval_parse_args_defaults_to_hierarchical_strategy(monkeypatch) -> None:
    script = _load_safe_eval_script()
    monkeypatch.setattr(sys, "argv", ["run_safe_chunking_eval.py"])

    args = script.parse_args()

    assert args.strategies == ("hierarchical_header_recursive",)


def test_safe_eval_parse_strategy_names_allows_explicit_active_strategies() -> None:
    script = _load_safe_eval_script()

    strategies = script.parse_strategy_names(
        "hierarchical_header_recursive, semantic_embedding"
    )

    assert strategies == ("hierarchical_header_recursive", "semantic_embedding")


def test_safe_eval_parse_strategy_names_rejects_unknown_strategy() -> None:
    script = _load_safe_eval_script()

    try:
        script.parse_strategy_names("unknown_strategy")
    except ValueError as exc:
        assert "unknown_strategy" in str(exc)
    else:
        raise AssertionError("Expected unknown chunking strategy to fail.")

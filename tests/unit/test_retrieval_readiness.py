import pytest

from src.services.document_retrieval.retrieval_readiness import (
    ProductionReadinessError,
    RetrievalReadinessReport,
)


def test_retrieval_readiness_passes_when_hybrid_and_indexes_exist() -> None:
    report = RetrievalReadinessReport(
        collection_name="insurevn_chunks",
        has_dense_vector=True,
        has_sparse_vector=True,
        missing_payload_indexes=[],
        dense_only_degraded=False,
    )

    report.assert_production_ready()


def test_retrieval_readiness_rejects_missing_sparse_vector() -> None:
    report = RetrievalReadinessReport(
        collection_name="insurevn_chunks",
        has_dense_vector=True,
        has_sparse_vector=False,
        missing_payload_indexes=[],
        dense_only_degraded=False,
    )

    with pytest.raises(ProductionReadinessError, match="sparse vector"):
        report.assert_production_ready()


def test_retrieval_readiness_rejects_missing_payload_indexes() -> None:
    report = RetrievalReadinessReport(
        collection_name="insurevn_chunks",
        has_dense_vector=True,
        has_sparse_vector=True,
        missing_payload_indexes=["company_code", "plan_code"],
        dense_only_degraded=False,
    )

    with pytest.raises(ProductionReadinessError, match="company_code, plan_code"):
        report.assert_production_ready()


def test_retrieval_readiness_rejects_dense_only_degraded_mode() -> None:
    report = RetrievalReadinessReport(
        collection_name="insurevn_chunks",
        has_dense_vector=True,
        has_sparse_vector=True,
        missing_payload_indexes=[],
        dense_only_degraded=True,
    )

    with pytest.raises(ProductionReadinessError, match="dense-only"):
        report.assert_production_ready()

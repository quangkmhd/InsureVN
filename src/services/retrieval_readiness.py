from dataclasses import dataclass

from src.services.observability import service_observe


class ProductionReadinessError(RuntimeError):
    """Raised when retrieval infrastructure is not production-ready."""


@dataclass(frozen=True)
class RetrievalReadinessReport:
    """Production readiness state for a retrieval collection."""

    collection_name: str
    has_dense_vector: bool
    has_sparse_vector: bool
    missing_payload_indexes: list[str]
    dense_only_degraded: bool

    @service_observe(
        name="service.retrieval_readiness.assert_production_ready",
        component="retrieval_readiness",
    )
    def assert_production_ready(self) -> None:
        """Raise when the retrieval collection cannot satisfy production gates."""
        failures: list[str] = []
        if not self.has_dense_vector:
            failures.append("missing dense vector")
        if not self.has_sparse_vector:
            failures.append("missing sparse vector")
        if self.missing_payload_indexes:
            failures.append(
                "missing payload indexes: " + ", ".join(self.missing_payload_indexes)
            )
        if self.dense_only_degraded:
            failures.append("dense-only degraded mode is not production-ready")

        if failures:
            raise ProductionReadinessError(
                f"{self.collection_name} is not production-ready: "
                + "; ".join(failures)
            )

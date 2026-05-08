"""Qdrant local vector databases for strategy-specific chunk indexes."""

from __future__ import annotations

import shutil
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.eval.embeddings import BenchmarkEmbeddings
from src.eval.models import RetrievedChunk, TextChunk


class QdrantStrategyDatabase:
    """One local Qdrant database directory for one chunking strategy."""

    def __init__(
        self,
        database_path: Path,
        collection_name: str,
        embeddings: BenchmarkEmbeddings,
    ) -> None:
        self.database_path = database_path
        self.collection_name = collection_name
        self.embeddings = embeddings
        self.client: QdrantClient | None = None

    def rebuild(self, chunks: list[TextChunk]) -> None:
        """Create a fresh local Qdrant database and index chunks into it."""

        if self.database_path.exists():
            shutil.rmtree(self.database_path)
        self.database_path.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(self.database_path))
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=vector_dimension(chunks, self.embeddings),
                distance=Distance.COSINE,
            ),
        )
        point_id = 0
        for batch_start in range(0, len(chunks), self.embeddings.batch_size):
            batch = chunks[batch_start : batch_start + self.embeddings.batch_size]
            vectors = build_batch_vectors(batch, self.embeddings)
            points = [
                PointStruct(
                    id=point_id + offset,
                    vector=vector,
                    payload=chunk.to_payload(),
                )
                for offset, (chunk, vector) in enumerate(
                    zip(batch, vectors, strict=True)
                )
            ]
            self.client.upsert(collection_name=self.collection_name, points=points)
            point_id += len(batch)

    def search(
        self,
        case_id: str,
        strategy: str,
        query: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        """Retrieve top-k chunks for a query."""

        if self.client is None:
            self.client = QdrantClient(path=str(self.database_path))
        query_vector = self.embeddings.embed_query(query)
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        retrieved: list[RetrievedChunk] = []
        for rank, point in enumerate(response.points, start=1):
            payload = point.payload or {}
            retrieved.append(
                RetrievedChunk(
                    case_id=case_id,
                    strategy=strategy,
                    rank=rank,
                    score=float(point.score),
                    chunk_id=str(payload.get("chunk_id", point.id)),
                    source_path=str(payload.get("source_path", "")),
                    provider=str(payload.get("provider", "")),
                    text=str(payload.get("text", "")),
                    start_line=int(payload.get("start_line", 0)),
                    end_line=int(payload.get("end_line", 0)),
                    metadata=dict(payload.get("metadata", {})),
                )
            )
        return retrieved

    def close(self) -> None:
        """Close the local Qdrant client."""

        if self.client is not None:
            self.client.close()
            self.client = None


def vector_dimension(chunks: list[TextChunk], embeddings: BenchmarkEmbeddings) -> int:
    """Return collection vector dimension from precomputed or live embeddings."""

    for chunk in chunks:
        if chunk.embedding is not None:
            return len(chunk.embedding)
    return embeddings.dimension


def build_batch_vectors(
    batch: list[TextChunk],
    embeddings: BenchmarkEmbeddings,
) -> list[list[float]]:
    """Use precomputed chunk vectors when available."""

    vectors: list[list[float] | None] = [None] * len(batch)
    missing_indices: list[int] = []
    missing_texts: list[str] = []
    for index, chunk in enumerate(batch):
        if chunk.embedding is not None:
            vectors[index] = chunk.embedding
        else:
            missing_indices.append(index)
            missing_texts.append(chunk.text)
    if missing_texts:
        embedded_texts = embeddings.embed_documents(missing_texts)
        for index, vector in zip(missing_indices, embedded_texts, strict=True):
            vectors[index] = vector
    if any(vector is None for vector in vectors):
        msg = "Unable to build vectors for every chunk in the batch."
        raise ValueError(msg)
    return [vector for vector in vectors if vector is not None]

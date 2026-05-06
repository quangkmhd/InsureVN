"""AI-assisted schema discovery for Vietnamese insurance policy documents."""

from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Protocol

from src.core.config import Settings, settings
from src.core.logger import get_logger
from src.services.observability import service_observe

SchemaDiscoveryProvider = Literal["ollama", "openrouter", "nvidia", "gemini"]

logger = get_logger(__name__)


@dataclass(frozen=True)
class SchemaDiscoveryChunk:
    """A resumable markdown text unit for schema discovery."""

    chunk_id: str
    file_path: str
    chunk_index: int
    text: str
    content_hash: str


@dataclass(frozen=True)
class SchemaDiscoveryProviderSlot:
    """One concurrent schema discovery worker backed by one provider credential."""

    slot_id: str
    provider: SchemaDiscoveryProvider
    model: str
    api_key: str = ""
    base_url: str = ""


@dataclass(frozen=True)
class SchemaNodeProposal:
    """A candidate graph node schema proposed from source text."""

    label: str
    vietnamese_aliases: list[str]
    description: str
    evidence_text: str
    confidence: float


@dataclass(frozen=True)
class SchemaRelationshipProposal:
    """A candidate graph relationship schema proposed from source text."""

    source_label: str
    relationship_label: str
    target_label: str
    vietnamese_aliases: list[str]
    description: str
    evidence_text: str
    confidence: float


@dataclass(frozen=True)
class SchemaChunkDiscoveryResult:
    """Schema discovery output for a single markdown chunk."""

    chunk_id: str
    file_path: str
    content_hash: str
    provider_slot_id: str
    nodes: list[SchemaNodeProposal]
    relationships: list[SchemaRelationshipProposal]
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AggregatedSchemaItem:
    """Aggregated schema proposal counts and lineage."""

    label: str
    occurrence_count: int
    source_files: list[str]
    aliases: list[str]
    examples: list[str]
    average_confidence: float


@dataclass(frozen=True)
class FileSchemaSummary:
    """Per-file schema labels after canonicalization."""

    node_labels: list[str]
    relationship_labels: list[str]


@dataclass(frozen=True)
class SchemaDiscoverySummary:
    """Corpus-level schema discovery summary."""

    nodes: dict[str, AggregatedSchemaItem]
    relationships: dict[str, AggregatedSchemaItem]
    per_file: dict[str, FileSchemaSummary]


@dataclass(frozen=True)
class SchemaCanonicalizationMap:
    """AI-proposed canonical schema label mappings."""

    node_map: dict[str, str]
    relationship_map: dict[str, str]


class SchemaDiscoveryClient(Protocol):
    """Client interface used by the resumable discovery runner."""

    async def discover_chunk_schema(
        self,
        chunk: SchemaDiscoveryChunk,
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaChunkDiscoveryResult:
        """Discover candidate schema from one chunk using one provider slot."""


class SchemaCanonicalizationClient(Protocol):
    """Client interface for merging similar schema labels."""

    async def canonicalize_schema_labels(
        self,
        *,
        node_items: list[AggregatedSchemaItem],
        relationship_items: list[AggregatedSchemaItem],
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaCanonicalizationMap:
        """Return canonical labels for similar node and relationship proposals."""


class MarkdownSchemaDiscoveryChunker:
    """Split markdown files into stable, large chunks for AI schema discovery."""

    def __init__(self, *, max_chunk_chars: int, overlap_chars: int = 0) -> None:
        """Initialize the chunker."""
        if max_chunk_chars <= 0:
            raise ValueError("max_chunk_chars must be positive.")
        if overlap_chars < 0:
            raise ValueError("overlap_chars cannot be negative.")
        if overlap_chars >= max_chunk_chars:
            raise ValueError("overlap_chars must be smaller than max_chunk_chars.")
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars

    @service_observe(
        name="service.knowledge_graph.schema_discovery.chunk_files",
        component="schema_discovery",
    )
    def chunk_files(self, file_paths: list[Path]) -> list[SchemaDiscoveryChunk]:
        """Load markdown files and return resumable AI scan chunks."""
        chunks: list[SchemaDiscoveryChunk] = []
        for file_path in sorted(file_paths):
            text = unicodedata.normalize(
                "NFC",
                file_path.read_text(encoding="utf-8"),
            )
            for chunk_index, chunk_text in enumerate(self._split_text(text)):
                content_hash = sha256(chunk_text.encode("utf-8")).hexdigest()
                stable_path = file_path.as_posix()
                chunks.append(
                    SchemaDiscoveryChunk(
                        chunk_id=f"{_stable_slug(stable_path)}:{chunk_index}",
                        file_path=stable_path,
                        chunk_index=chunk_index,
                        text=chunk_text,
                        content_hash=content_hash,
                    )
                )
        return chunks

    def _split_text(self, text: str) -> list[str]:
        sections = _split_markdown_sections(text)
        chunks: list[str] = []
        current = ""
        for section in sections:
            if not current:
                current = section
                continue
            if len(current) + len(section) + 2 <= self.max_chunk_chars:
                current = f"{current}\n\n{section}"
                continue
            chunks.extend(self._split_oversized_text(current))
            current = section
        if current:
            chunks.extend(self._split_oversized_text(current))
        return [chunk for chunk in chunks if chunk.strip()]

    def _split_oversized_text(self, text: str) -> list[str]:
        if len(text) <= self.max_chunk_chars:
            return [text.strip()]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.max_chunk_chars, len(text))
            chunks.append(text[start:end].strip())
            if end == len(text):
                break
            start = max(end - self.overlap_chars, start + 1)
        return chunks


class SchemaDiscoveryCheckpointStore:
    """JSONL checkpoint store for resumable schema discovery runs."""

    def __init__(self, path: Path) -> None:
        """Initialize checkpoint storage."""
        self.path = path

    @service_observe(
        name="service.knowledge_graph.schema_discovery.record_success",
        component="schema_discovery",
    )
    def record_success(
        self,
        chunk: SchemaDiscoveryChunk,
        result: SchemaChunkDiscoveryResult,
    ) -> None:
        """Persist a successful chunk result."""
        self._append_record(
            {
                "status": "success",
                "chunk_id": chunk.chunk_id,
                "content_hash": chunk.content_hash,
                "file_path": chunk.file_path,
                "provider_slot_id": result.provider_slot_id,
                "result": _chunk_result_to_dict(result),
            }
        )

    @service_observe(
        name="service.knowledge_graph.schema_discovery.record_error",
        component="schema_discovery",
    )
    def record_error(
        self,
        chunk: SchemaDiscoveryChunk,
        *,
        provider_slot_id: str,
        error_message: str,
        error_type: str | None = None,
    ) -> None:
        """Persist a failed chunk attempt."""
        self._append_record(
            {
                "status": "error",
                "chunk_id": chunk.chunk_id,
                "content_hash": chunk.content_hash,
                "file_path": chunk.file_path,
                "provider_slot_id": provider_slot_id,
                "error_type": error_type,
                "error_message": error_message,
            }
        )

    def successful_chunk_ids(self, chunks: list[SchemaDiscoveryChunk]) -> set[str]:
        """Return chunk IDs with matching latest successful records."""
        latest_records = self._latest_records()
        successful_ids: set[str] = set()
        for chunk in chunks:
            record = latest_records.get(chunk.chunk_id)
            if (
                record
                and record.get("status") == "success"
                and record.get("content_hash") == chunk.content_hash
            ):
                successful_ids.add(chunk.chunk_id)
        return successful_ids

    def result_for_chunk(
        self,
        chunk: SchemaDiscoveryChunk,
    ) -> SchemaChunkDiscoveryResult | None:
        """Return the latest successful result for a chunk, if still current."""
        record = self._latest_records().get(chunk.chunk_id)
        if (
            not record
            or record.get("status") != "success"
            or record.get("content_hash") != chunk.content_hash
        ):
            return None
        result_payload = record.get("result")
        if not isinstance(result_payload, dict):
            return None
        return _chunk_result_from_dict(result_payload)

    def _append_record(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as checkpoint_file:
            checkpoint_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _latest_records(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        records: dict[str, dict[str, Any]] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            chunk_id = record.get("chunk_id")
            if isinstance(chunk_id, str):
                records[chunk_id] = record
        return records


class SchemaDiscoveryRunner:
    """Run schema discovery concurrently while respecting checkpoint state."""

    def __init__(
        self,
        *,
        checkpoint_store: SchemaDiscoveryCheckpointStore,
        provider_slots: list[SchemaDiscoveryProviderSlot],
        max_concurrency: int,
        max_retries: int = 2,
        attempt_timeout_seconds: float = 90.0,
    ) -> None:
        """Initialize the runner."""
        if not provider_slots:
            raise ValueError("At least one schema discovery provider slot is required.")
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive.")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        if attempt_timeout_seconds <= 0:
            raise ValueError("attempt_timeout_seconds must be positive.")
        self.checkpoint_store = checkpoint_store
        self.provider_slots = provider_slots[:max_concurrency]
        self.max_retries = max_retries
        self.attempt_timeout_seconds = attempt_timeout_seconds

    @service_observe(
        name="service.knowledge_graph.schema_discovery.run",
        component="schema_discovery",
    )
    async def run(
        self,
        *,
        chunks: list[SchemaDiscoveryChunk],
        client: SchemaDiscoveryClient,
    ) -> list[SchemaChunkDiscoveryResult]:
        """Process only chunks without a current successful checkpoint."""
        queue: asyncio.Queue[SchemaDiscoveryChunk] = asyncio.Queue()
        completed_results: dict[str, SchemaChunkDiscoveryResult] = {}
        for chunk in chunks:
            existing_result = self.checkpoint_store.result_for_chunk(chunk)
            if existing_result is not None:
                completed_results[chunk.chunk_id] = existing_result
                continue
            queue.put_nowait(chunk)

        async def worker(slot: SchemaDiscoveryProviderSlot) -> None:
            while True:
                try:
                    chunk = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    result = await self._discover_with_retries(
                        chunk=chunk,
                        slot=slot,
                        client=client,
                    )
                    self.checkpoint_store.record_success(chunk, result)
                    completed_results[chunk.chunk_id] = result
                except Exception as exc:
                    self.checkpoint_store.record_error(
                        chunk,
                        provider_slot_id=slot.slot_id,
                        error_type=type(exc).__name__,
                        error_message=_error_message(exc),
                    )
                    logger.warning(
                        "schema discovery chunk failed",
                        extra={
                            "component": "schema_discovery",
                            "chunk_id": chunk.chunk_id,
                            "file_path": chunk.file_path,
                            "provider_slot_id": slot.slot_id,
                            "error_type": type(exc).__name__,
                        },
                    )
                finally:
                    queue.task_done()

        await asyncio.gather(*(worker(slot) for slot in self.provider_slots))
        return [
            completed_results[chunk.chunk_id]
            for chunk in chunks
            if chunk.chunk_id in completed_results
        ]

    async def _discover_with_retries(
        self,
        *,
        chunk: SchemaDiscoveryChunk,
        slot: SchemaDiscoveryProviderSlot,
        client: SchemaDiscoveryClient,
    ) -> SchemaChunkDiscoveryResult:
        for attempt_index in range(self.max_retries + 1):
            try:
                async with asyncio.timeout(self.attempt_timeout_seconds):
                    return await client.discover_chunk_schema(chunk, slot)
            except TimeoutError as exc:
                timeout_message = (
                    "schema discovery provider attempt exceeded "
                    f"{self.attempt_timeout_seconds:g}s"
                )
                if attempt_index >= self.max_retries:
                    raise TimeoutError(timeout_message) from exc
                logger.warning(
                    "schema discovery chunk attempt timed out; retrying",
                    extra={
                        "component": "schema_discovery",
                        "chunk_id": chunk.chunk_id,
                        "file_path": chunk.file_path,
                        "provider_slot_id": slot.slot_id,
                        "attempt_number": attempt_index + 1,
                        "max_retries": self.max_retries,
                        "timeout_seconds": self.attempt_timeout_seconds,
                    },
                )
            except Exception as exc:
                if attempt_index >= self.max_retries:
                    raise
                logger.warning(
                    "schema discovery chunk attempt failed; retrying",
                    extra={
                        "component": "schema_discovery",
                        "chunk_id": chunk.chunk_id,
                        "file_path": chunk.file_path,
                        "provider_slot_id": slot.slot_id,
                        "attempt_number": attempt_index + 1,
                        "max_retries": self.max_retries,
                        "error_type": type(exc).__name__,
                    },
                )
        raise RuntimeError("unreachable schema discovery retry state")


class SchemaDiscoveryAggregator:
    """Aggregate raw schema proposals into per-file and corpus summaries."""

    @service_observe(
        name="service.knowledge_graph.schema_discovery.aggregate",
        component="schema_discovery",
    )
    def aggregate(
        self,
        results: list[SchemaChunkDiscoveryResult],
        *,
        canonical_node_map: dict[str, str] | None = None,
        canonical_relationship_map: dict[str, str] | None = None,
    ) -> SchemaDiscoverySummary:
        """Aggregate raw chunk results using optional AI-provided canonical maps."""
        node_map = canonical_node_map or {}
        relationship_map = canonical_relationship_map or {}
        node_buckets: dict[str, list[SchemaNodeProposal]] = {}
        relationship_buckets: dict[str, list[SchemaRelationshipProposal]] = {}
        node_files: dict[str, list[str]] = {}
        relationship_files: dict[str, list[str]] = {}
        per_file_nodes: dict[str, list[str]] = {}
        per_file_relationships: dict[str, list[str]] = {}

        for result in results:
            for node in result.nodes:
                canonical_label = node_map.get(node.label, node.label)
                node_buckets.setdefault(canonical_label, []).append(node)
                _append_unique(
                    node_files.setdefault(canonical_label, []),
                    result.file_path,
                )
                _append_unique(
                    per_file_nodes.setdefault(result.file_path, []),
                    canonical_label,
                )

            for relationship in result.relationships:
                canonical_label = relationship_map.get(
                    relationship.relationship_label,
                    relationship.relationship_label,
                )
                relationship_buckets.setdefault(canonical_label, []).append(
                    relationship
                )
                _append_unique(
                    relationship_files.setdefault(canonical_label, []),
                    result.file_path,
                )
                _append_unique(
                    per_file_relationships.setdefault(result.file_path, []),
                    canonical_label,
                )

        per_file = {
            file_path: FileSchemaSummary(
                node_labels=sorted(set(per_file_nodes.get(file_path, []))),
                relationship_labels=sorted(
                    set(per_file_relationships.get(file_path, []))
                ),
            )
            for file_path in sorted(set(per_file_nodes) | set(per_file_relationships))
        }
        return SchemaDiscoverySummary(
            nodes={
                label: _aggregate_nodes(label, proposals, node_files[label])
                for label, proposals in sorted(node_buckets.items())
            },
            relationships={
                label: _aggregate_relationships(
                    label,
                    proposals,
                    relationship_files[label],
                )
                for label, proposals in sorted(relationship_buckets.items())
            },
            per_file=per_file,
        )


class SchemaDiscoveryCanonicalizer:
    """Ask AI to merge similar schema labels into canonical labels."""

    @service_observe(
        name="service.knowledge_graph.schema_discovery.canonicalize",
        component="schema_discovery",
    )
    async def canonicalize(
        self,
        *,
        raw_summary: SchemaDiscoverySummary,
        client: SchemaCanonicalizationClient,
        slot: SchemaDiscoveryProviderSlot,
        fallback_to_identity: bool = False,
    ) -> SchemaCanonicalizationMap:
        """Canonicalize discovered node and relationship labels using AI."""
        try:
            return await client.canonicalize_schema_labels(
                node_items=list(raw_summary.nodes.values()),
                relationship_items=list(raw_summary.relationships.values()),
                slot=slot,
            )
        except Exception as exc:
            if not fallback_to_identity:
                raise
            logger.warning(
                "schema canonicalization failed; using identity map",
                extra={
                    "component": "schema_discovery",
                    "slot_id": slot.slot_id,
                    "provider": slot.provider,
                    "model": slot.model,
                    "error_type": type(exc).__name__,
                },
            )
            return SchemaCanonicalizationMap(
                node_map={label: label for label in raw_summary.nodes},
                relationship_map={label: label for label in raw_summary.relationships},
            )


def build_provider_slots_from_settings(
    app_settings: Settings = settings,
) -> list[SchemaDiscoveryProviderSlot]:
    """Build provider slots from configured Ollama/API-key lists."""
    slots: list[SchemaDiscoveryProviderSlot] = []
    ollama_base_urls = app_settings.KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS
    ollama_api_keys = app_settings.KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS
    if ollama_api_keys:
        for index, api_key in enumerate(ollama_api_keys):
            base_url = ollama_base_urls[index % len(ollama_base_urls)]
            slots.append(
                SchemaDiscoveryProviderSlot(
                    slot_id=f"ollama-{index}",
                    provider="ollama",
                    model=app_settings.KG_SCHEMA_DISCOVERY_OLLAMA_MODEL,
                    api_key=api_key,
                    base_url=base_url,
                )
            )
    for index, base_url in enumerate([] if ollama_api_keys else ollama_base_urls):
        slots.append(
            SchemaDiscoveryProviderSlot(
                slot_id=f"ollama-{index}",
                provider="ollama",
                model=app_settings.KG_SCHEMA_DISCOVERY_OLLAMA_MODEL,
                base_url=base_url,
            )
        )
    for index, api_key in enumerate(
        app_settings.KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS
    ):
        slots.append(
            SchemaDiscoveryProviderSlot(
                slot_id=f"openrouter-{index}",
                provider="openrouter",
                model=app_settings.KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL,
                api_key=api_key,
                base_url=app_settings.KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL,
            )
        )
    for index, api_key in enumerate(app_settings.KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS):
        slots.append(
            SchemaDiscoveryProviderSlot(
                slot_id=f"nvidia-{index}",
                provider="nvidia",
                model=app_settings.KG_SCHEMA_DISCOVERY_NVIDIA_MODEL,
                api_key=api_key,
                base_url=app_settings.KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL,
            )
        )
    for index, api_key in enumerate(app_settings.KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS):
        slots.append(
            SchemaDiscoveryProviderSlot(
                slot_id=f"gemini-{index}",
                provider="gemini",
                model=app_settings.KG_SCHEMA_DISCOVERY_GEMINI_MODEL,
                api_key=api_key,
                base_url=app_settings.KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL,
            )
        )
    return slots


def find_markdown_files(input_path: Path) -> list[Path]:
    """Find markdown and text files under the input path."""
    if input_path.is_file():
        return [input_path]
    return sorted(
        file_path
        for file_path in input_path.rglob("*")
        if file_path.suffix.lower() in {".md", ".markdown", ".txt"}
    )


def write_summary_json(summary: SchemaDiscoverySummary, path: Path) -> None:
    """Write schema discovery summary JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_schema_discovery_markdown_report(
    summary: SchemaDiscoverySummary,
    path: Path,
) -> None:
    """Write a human-readable schema discovery report."""
    lines = [
        "# Knowledge Graph Schema Discovery Report",
        "",
        "## Nodes",
        "",
        "| Label | Occurrences | Files | Avg Confidence | Aliases |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for item in summary.nodes.values():
        lines.append(
            "| "
            + " | ".join(
                [
                    item.label,
                    str(item.occurrence_count),
                    str(len(item.source_files)),
                    f"{item.average_confidence:.4f}",
                    ", ".join(item.aliases),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Relationships",
            "",
            "| Label | Occurrences | Files | Avg Confidence | Aliases |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for item in summary.relationships.values():
        lines.append(
            "| "
            + " | ".join(
                [
                    item.label,
                    str(item.occurrence_count),
                    str(len(item.source_files)),
                    f"{item.average_confidence:.4f}",
                    ", ".join(item.aliases),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Per File",
            "",
            "| File | Nodes | Relationships |",
            "| --- | --- | --- |",
        ]
    )
    for file_path, file_summary in summary.per_file.items():
        lines.append(
            "| "
            + " | ".join(
                [
                    file_path,
                    ", ".join(file_summary.node_labels),
                    ", ".join(file_summary.relationship_labels),
                ]
            )
            + " |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _split_markdown_sections(text: str) -> list[str]:
    matches = list(re.finditer(r"^(#{1,6})\s+.+?\s*$", text, flags=re.MULTILINE))
    if not matches:
        return [text.strip()] if text.strip() else []
    sections: list[str] = []
    if matches[0].start() > 0:
        preface = text[: matches[0].start()].strip()
        if preface:
            sections.append(preface)
    for index, match in enumerate(matches):
        next_start = (
            matches[index + 1].start() if index + 1 < len(matches) else len(text)
        )
        section = text[match.start() : next_start].strip()
        if section:
            sections.append(section)
    return sections


def _chunk_result_to_dict(result: SchemaChunkDiscoveryResult) -> dict[str, Any]:
    return asdict(result)


def _chunk_result_from_dict(payload: dict[str, Any]) -> SchemaChunkDiscoveryResult:
    return SchemaChunkDiscoveryResult(
        chunk_id=str(payload["chunk_id"]),
        file_path=str(payload["file_path"]),
        content_hash=str(payload["content_hash"]),
        provider_slot_id=str(payload["provider_slot_id"]),
        nodes=[
            SchemaNodeProposal(
                label=str(node["label"]),
                vietnamese_aliases=[str(item) for item in node["vietnamese_aliases"]],
                description=str(node["description"]),
                evidence_text=str(node["evidence_text"]),
                confidence=float(node["confidence"]),
            )
            for node in payload.get("nodes", [])
            if isinstance(node, dict)
        ],
        relationships=[
            SchemaRelationshipProposal(
                source_label=str(relationship["source_label"]),
                relationship_label=str(relationship["relationship_label"]),
                target_label=str(relationship["target_label"]),
                vietnamese_aliases=[
                    str(item) for item in relationship["vietnamese_aliases"]
                ],
                description=str(relationship["description"]),
                evidence_text=str(relationship["evidence_text"]),
                confidence=float(relationship["confidence"]),
            )
            for relationship in payload.get("relationships", [])
            if isinstance(relationship, dict)
        ],
        usage=dict(payload.get("usage", {})),
    )


def _aggregate_nodes(
    label: str,
    proposals: list[SchemaNodeProposal],
    source_files: list[str],
) -> AggregatedSchemaItem:
    aliases: list[str] = []
    examples: list[str] = []
    for proposal in proposals:
        for alias in proposal.vietnamese_aliases:
            _append_unique(aliases, alias)
        _append_unique(examples, proposal.evidence_text)
    return AggregatedSchemaItem(
        label=label,
        occurrence_count=len(proposals),
        source_files=source_files,
        aliases=aliases,
        examples=examples[:5],
        average_confidence=_average([proposal.confidence for proposal in proposals]),
    )


def _aggregate_relationships(
    label: str,
    proposals: list[SchemaRelationshipProposal],
    source_files: list[str],
) -> AggregatedSchemaItem:
    aliases: list[str] = []
    examples: list[str] = []
    for proposal in proposals:
        for alias in proposal.vietnamese_aliases:
            _append_unique(aliases, alias)
        _append_unique(examples, proposal.evidence_text)
    return AggregatedSchemaItem(
        label=label,
        occurrence_count=len(proposals),
        source_files=source_files,
        aliases=aliases,
        examples=examples[:5],
        average_confidence=_average([proposal.confidence for proposal in proposals]),
    )


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    return repr(exc)


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _stable_slug(value: str) -> str:
    normalized_value = unicodedata.normalize("NFKD", value)
    ascii_value = normalized_value.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value.lower()).strip("_")
    return slug or "unknown"

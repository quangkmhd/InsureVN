"""Context-enriched chunking example from the Databricks RAG chunking guide."""

from __future__ import annotations

from typing import Any

from common import create_dummy_document
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    from databricks_langchain import ChatDatabricks
except ImportError:  # pragma: no cover - optional local dependency
    ChatDatabricks = None


def _summary_text(response: Any) -> str:
    """Normalize model responses to plain text."""
    return str(getattr(response, "content", response))


def perform_context_enriched_chunking(
    document: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    window_size: int = 1,
    summarize: bool = True,
) -> list[Document]:
    """Perform context-enriched chunking using neighboring chunks as context."""
    if summarize and ChatDatabricks is None:
        raise ImportError(
            "databricks-langchain is required for Databricks summarization. "
            "Use perform_context_enriched_chunking_mock for local testing."
        )

    chat_model = None
    summary_chain = None
    if summarize:
        chat_model = ChatDatabricks(
            endpoint="databricks-meta-llama-3-3-70b-instruct",
            temperature=0.1,
            max_tokens=250,
        )
        summary_prompt = PromptTemplate.from_template(
            "Provide a brief summary of the following text:\n\n{text}\n\nSummary:"
        )
        summary_chain = summary_prompt | chat_model

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    base_chunks = splitter.split_text(document)
    print(f"Document split into {len(base_chunks)} base chunks")

    enriched_documents = []
    for i, chunk in enumerate(base_chunks):
        print(f"Processing chunk {i + 1}/{len(base_chunks)}")
        window_start = max(0, i - window_size)
        window_end = min(len(base_chunks), i + window_size + 1)
        window = base_chunks[window_start:window_end]
        context_chunks = [
            item for j, item in enumerate(window) if j != i - window_start
        ]
        context_text = " ".join(context_chunks)
        metadata: dict[str, Any] = {
            "chunk_id": i,
            "total_chunks": len(base_chunks),
            "chunk_size": len(chunk),
            "window_start_idx": window_start,
            "window_end_idx": window_end - 1,
            "has_context": len(context_chunks) > 0,
        }

        if context_chunks and summarize and summary_chain is not None:
            try:
                context_summary = _summary_text(
                    summary_chain.invoke({"text": context_text})
                )
                metadata["context"] = context_summary
                metadata["context_type"] = "summary"
                enriched_text = f"Context: {context_summary}\n\nContent: {chunk}"
            except Exception as exc:  # pragma: no cover - external API fallback
                print(f"Summarization error for chunk {i}: {exc}")
                metadata["context"] = context_text
                metadata["context_type"] = "raw_text"
                metadata["summary_error"] = str(exc)
                enriched_text = f"Context: {context_text}\n\nContent: {chunk}"
        elif context_chunks:
            metadata["context"] = context_text
            metadata["context_type"] = "raw_text"
            enriched_text = f"Context: {context_text}\n\nContent: {chunk}"
        else:
            metadata["context"] = ""
            metadata["context_type"] = "none"
            enriched_text = chunk

        enriched_documents.append(
            Document(page_content=enriched_text, metadata=metadata)
        )

    return enriched_documents


class MockChatModel:
    """Mock LLM for testing without Databricks."""

    def __init__(self, **kwargs: Any) -> None:
        """Store mock keyword arguments for inspection."""
        self.kwargs = kwargs

    def invoke(self, input_text: Any) -> str:
        """Generate a simple summary based on the first sentence."""
        if (
            isinstance(input_text, list)
            and input_text
            and hasattr(input_text[0], "page_content")
        ):
            text = input_text[0].page_content
        else:
            text = str(input_text)
        first_sentence = text.split(".")[0]
        return f"Summary: {first_sentence[:100]}..."


def perform_context_enriched_chunking_mock(
    document: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    window_size: int = 1,
) -> list[Document]:
    """Mock context-enriched chunking for testing without Databricks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    base_chunks = splitter.split_text(document)
    print(f"Document split into {len(base_chunks)} base chunks")

    def mock_summarize(text: str) -> str:
        first_sentence = text.split(".")[0]
        return f"Summary: {first_sentence[:100]}..."

    enriched_documents = []
    for i, chunk in enumerate(base_chunks):
        window_start = max(0, i - window_size)
        window_end = min(len(base_chunks), i + window_size + 1)
        window = base_chunks[window_start:window_end]
        context_chunks = [
            item for j, item in enumerate(window) if j != i - window_start
        ]
        context_text = " ".join(context_chunks)

        if context_chunks:
            context_summary = mock_summarize(context_text)
            metadata = {
                "chunk_id": i,
                "total_chunks": len(base_chunks),
                "context": context_summary,
                "context_type": "summary",
            }
            enriched_text = f"Context: {context_summary}\n\nContent: {chunk}"
        else:
            metadata = {
                "chunk_id": i,
                "total_chunks": len(base_chunks),
                "context": "",
                "context_type": "none",
            }
            enriched_text = chunk

        enriched_documents.append(
            Document(page_content=enriched_text, metadata=metadata)
        )

    return enriched_documents


if __name__ == "__main__":
    demo_document = create_dummy_document()
    print("Using mock implementation for testing...")
    enriched_docs = perform_context_enriched_chunking_mock(
        demo_document,
        chunk_size=500,
        chunk_overlap=50,
        window_size=1,
    )

    print("\n----- CHUNKING RESULTS -----")
    print(f"Total enriched chunks: {len(enriched_docs)}")
    print("\n----- EXAMPLE ENRICHED CHUNK -----")
    middle_chunk_idx = len(enriched_docs) // 2
    example_chunk = enriched_docs[middle_chunk_idx]
    print(f"Chunk {middle_chunk_idx} with context:")
    print("-" * 40)
    print(example_chunk.page_content)
    print("-" * 40)
    print(f"Metadata: {example_chunk.metadata}")
    print("\nTo use with Databricks:")
    print("1. Replace perform_context_enriched_chunking_mock with")
    print("   perform_context_enriched_chunking")
    print("2. Ensure your Databricks endpoint is correctly configured")
    print("3. Store documents with context in Delta table")
    print("4. Create embeddings that include the context information")

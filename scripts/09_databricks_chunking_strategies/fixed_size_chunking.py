"""Fixed-size chunking example from the Databricks RAG chunking guide."""

from __future__ import annotations

from common import create_dummy_document, print_example_chunk
from langchain_core.documents import Document
from langchain_text_splitters import CharacterTextSplitter


def perform_fixed_size_chunking(
    document: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[Document]:
    """Perform fixed-size chunking on a document with specified overlap."""
    text_splitter = CharacterTextSplitter(
        separator="\n\n",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    chunks = text_splitter.split_text(document)
    print(f"Document split into {len(chunks)} chunks")

    documents = []
    for i, chunk in enumerate(chunks):
        documents.append(
            Document(
                page_content=chunk,
                metadata={
                    "chunk_id": i,
                    "total_chunks": len(chunks),
                    "chunk_size": len(chunk),
                    "chunk_type": "fixed-size",
                },
            )
        )

    return documents


if __name__ == "__main__":
    demo_document = create_dummy_document()
    chunked_docs = perform_fixed_size_chunking(
        demo_document,
        chunk_size=1000,
        chunk_overlap=200,
    )

    print("\n----- CHUNKING RESULTS -----")
    print(f"Total chunks: {len(chunked_docs)}")
    print_example_chunk(chunked_docs)
    print("\nThese documents are ready for embedding and storage in")
    print("Databricks Vector Search")
    print("Example next steps:")
    print("1. Create embeddings using the Databricks embedding endpoint")
    print("2. Store documents and embeddings in Delta table")
    print("3. Create Vector Search index for retrieval")

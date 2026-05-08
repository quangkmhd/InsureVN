"""Recursive code chunking example from the Databricks RAG chunking guide."""

from __future__ import annotations

import re

from langchain_core.documents import Document
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter


def _language_enum(language: str) -> Language | None:
    """Return a LangChain language enum for a supported code language."""
    language_map = {
        "python": getattr(Language, "PYTHON", None),
        "javascript": getattr(Language, "JS", None),
        "js": getattr(Language, "JS", None),
        "java": getattr(Language, "JAVA", None),
        "go": getattr(Language, "GO", None),
        "rust": getattr(Language, "RUST", None),
    }
    return language_map.get(language.lower())


def perform_code_chunking(
    code_document: str,
    language: str = "python",
    chunk_size: int = 100,
    chunk_overlap: int = 15,
) -> list[Document]:
    """Perform recursive chunking on code documents."""
    language_value = _language_enum(language)
    if language_value is not None:
        code_splitter = RecursiveCharacterTextSplitter.from_language(
            language=language_value,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    else:
        code_splitter = RecursiveCharacterTextSplitter(
            separators=["\nclass ", "\ndef ", "\n\n", "\n", " ", ""],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

    code_chunks = code_splitter.split_text(code_document)
    print(f"Code document split into {len(code_chunks)} chunks")

    documents = []
    for i, chunk in enumerate(code_chunks):
        function_match = re.search(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", chunk)
        class_match = re.search(r"class\s+([a-zA-Z_][a-zA-Z0-9_]*)", chunk)
        import_match = re.search(r"import\s+([a-zA-Z_][a-zA-Z0-9_\.]*)", chunk)

        chunk_type = "code_segment"
        if function_match:
            chunk_type = "function"
            structure_name = function_match.group(1)
        elif class_match:
            chunk_type = "class"
            structure_name = class_match.group(1)
        elif import_match:
            chunk_type = "import"
            structure_name = import_match.group(1)
        else:
            structure_name = f"segment_{i}"

        documents.append(
            Document(
                page_content=chunk,
                metadata={
                    "chunk_id": i,
                    "total_chunks": len(code_chunks),
                    "language": language,
                    "chunk_type": chunk_type,
                    "structure_name": structure_name,
                    "lines": chunk.count("\n") + 1,
                },
            )
        )

    return documents


def create_python_document() -> str:
    """Create a sample Python document for testing code chunking."""
    return '''
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score


def load_data(filepath):
    """Load data from CSV file."""
    df = pd.read_csv(filepath)
    print(f"Loaded data with {df.shape[0]} rows and {df.shape[1]} columns")
    return df


def preprocess_data(df, target_column):
    """Preprocess the data for training."""
    df = df.fillna(df.mean())
    x = df.drop(target_column, axis=1)
    y = df[target_column]
    return x, y


class ModelTrainer:
    """Class to handle model training and evaluation."""

    def __init__(self, model_type="rf", random_state=42):
        self.random_state = random_state
        if model_type == "rf":
            self.model = RandomForestClassifier(random_state=random_state)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

    def train(self, x, y, test_size=0.2):
        """Train the model with train-test split."""
        x_train, x_test, y_train, y_test = train_test_split(
            x,
            y,
            test_size=test_size,
            random_state=self.random_state,
        )
        self.model.fit(x_train, y_train)
        train_preds = self.model.predict(x_train)
        test_preds = self.model.predict(x_test)
        train_acc = accuracy_score(y_train, train_preds)
        test_acc = accuracy_score(y_test, test_preds)
        print(f"Training accuracy: {train_acc:.4f}")
        print(f"Testing accuracy: {test_acc:.4f}")
        return {
            "model": self.model,
            "x_test": x_test,
            "y_test": y_test,
            "test_acc": test_acc,
        }

    def get_feature_importance(self, feature_names):
        """Get feature importance from the model."""
        if not hasattr(self.model, "feature_importances_"):
            raise ValueError("Model does not have feature importances")
        importances = self.model.feature_importances_
        indices = np.argsort(importances)[::-1]
        return [
            {"feature": feature_names[i], "importance": importances[i]}
            for i in indices
        ]
'''.strip()


if __name__ == "__main__":
    python_document = create_python_document()
    chunked_docs = perform_code_chunking(
        python_document,
        language="python",
        chunk_size=100,
        chunk_overlap=15,
    )

    print("\n----- CHUNKING RESULTS -----")
    print(f"Total code chunks: {len(chunked_docs)}")

    chunk_types: dict[str, int] = {}
    for doc in chunked_docs:
        chunk_type = doc.metadata["chunk_type"]
        chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1

    print("\n----- CODE STRUCTURE BREAKDOWN -----")
    for chunk_type, count in chunk_types.items():
        print(f"{chunk_type}: {count} chunks")

    print("\n----- EXAMPLE FUNCTION CHUNK -----")
    function_chunks = [
        doc for doc in chunked_docs if doc.metadata["chunk_type"] == "function"
    ]
    if function_chunks:
        example_chunk = function_chunks[0]
        print(f"Function: {example_chunk.metadata['structure_name']}")
        print("-" * 40)
        print(example_chunk.page_content)
        print("-" * 40)

    print("\nTo use with Databricks:")
    print("1. Store code chunks in Delta table with metadata")
    print("2. Create embeddings using a Databricks embedding endpoint")
    print("3. Create Vector Search index for code retrieval")
    print("4. Use function/class metadata for filtering during retrieval")

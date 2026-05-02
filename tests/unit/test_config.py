import os
from src.core.config import settings

def test_langfuse_settings_loaded(monkeypatch):
    # Mock environment variables
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3000")
    
    # Re-evaluate the properties or ensure they are present
    assert hasattr(settings, "LANGFUSE_PUBLIC_KEY")
    assert hasattr(settings, "LANGFUSE_SECRET_KEY")
    assert hasattr(settings, "LANGFUSE_BASE_URL")
    
    # Ensure LangSmith variables are removed
    assert not hasattr(settings, "LANGCHAIN_TRACING_V2")

import os
from src.core.config import settings

def test_langsmith_settings_loaded(monkeypatch):
    # Mock environment variables
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "TestProject")
    
    # Re-evaluate the properties or ensure they are present
    assert hasattr(settings, "LANGCHAIN_TRACING_V2")
    assert hasattr(settings, "LANGCHAIN_PROJECT")

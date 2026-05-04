import importlib
import unittest


class TestProjectImports(unittest.TestCase):
    """Test that all core modules and third-party dependencies are importable."""

    def test_import_main(self):
        """Test that main is importable."""
        try:
            importlib.import_module("main")
        except ImportError as e:
            self.fail(f"Could not import main: {e}")

    def test_import_agents(self):
        """Test that core agents are importable."""
        modules = [
            "agents.database_agent",
            "tools.search_tool",
        ]
        for module_name in modules:
            with self.subTest(module=module_name):
                try:
                    importlib.import_module(module_name)
                except ImportError as e:
                    self.fail(f"Could not import {module_name}: {e}")

    def test_import_dependencies(self):
        """Test that third-party dependencies required for Phase 00+ are importable."""
        dependencies = [
            "fastapi",
            "uvicorn",
            "pydantic",
            "dotenv",
            "langchain",
            "langgraph",
            "langfuse",
            "qdrant_client",
            "networkx",
        ]
        for dep in dependencies:
            with self.subTest(dependency=dep):
                try:
                    importlib.import_module(dep)
                except ImportError as e:
                    self.fail(f"Could not import dependency {dep}: {e}")


if __name__ == "__main__":
    unittest.main()

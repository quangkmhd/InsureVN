import pytest
import os
import sys
from pathlib import Path

# Add scripts directory to path to import script
scripts_dir = Path(__file__).parent.parent.parent / "scripts" / "05_training_eval"
sys.path.append(str(scripts_dir))
import classify_json

def test_get_unprocessed_files(tmp_path):
    # Setup dummy environment
    input_dir = tmp_path / "input"
    good_dir = tmp_path / "good"
    trash_dir = tmp_path / "trash"
    
    input_dir.mkdir()
    good_dir.mkdir()
    trash_dir.mkdir()
    
    # Create input files
    (input_dir / "file1.json").write_text("{}")
    (input_dir / "file2.json").write_text("{}")
    (input_dir / "file3.json").write_text("{}")
    
    # Create already processed file in good_dir
    (good_dir / "file2.json").write_text("{}")
    
    # Create already processed file in trash_dir
    (trash_dir / "file3.json").write_text("{}")
    
    # Test function
    unprocessed = classify_json.get_unprocessed_files(input_dir, good_dir, trash_dir)
    assert len(unprocessed) == 1
    assert unprocessed[0].name == "file1.json"

def test_load_workers(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("OLLAMA_API_KEY_1=key1\nOLLAMA_API_KEY_2=key2\nNVIDIA_NIM_API_KEY=key3\n")
    
    # Create a dummy Path object that returns our tmp env_file when initialized
    class MockPath:
        def __init__(self, path):
            self.path = env_file
            
        def exists(self):
            return True
            
        def __truediv__(self, other):
            return self
            
        def __getattr__(self, name):
            return getattr(self.path, name)
            
        def __str__(self):
            return str(self.path)

    # We need to mock the Path object where it's used in load_workers
    monkeypatch.setattr(classify_json, "Path", lambda x: env_file)
    
    workers = classify_json.load_workers()
    assert len(workers) == 3
    assert any(w.provider == "OLLAMA" and w.api_key == "key1" for w in workers)
    assert any(w.provider == "OLLAMA" and w.api_key == "key2" for w in workers)
    assert any(w.provider == "NVIDIA" and w.api_key == "key3" for w in workers)
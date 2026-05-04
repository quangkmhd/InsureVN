import sqlite3
import importlib.util
import os

def load_seed_script():
    script_path = os.path.join(os.path.dirname(__file__), '../../scripts/06_db_ingestion/seed_synthetic_benchmark.py')
    spec = importlib.util.spec_from_file_location("seed_synthetic_benchmark", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_benchmark_seed(temp_db):
    seed_module = load_seed_script()
    
    # Seed the temporary database
    seed_module.seed_benchmark_cases(temp_db)
    
    # Verify the results
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM synthetic_benchmark_cases")
    count = cursor.fetchone()[0]
    
    assert count == 100, f"Expected 100 benchmark cases, but found {count}"
    
    cursor.execute("SELECT expected_intent_group, expected_risk_level, expected_workflow FROM synthetic_benchmark_cases LIMIT 1")
    first_case = cursor.fetchone()
    
    assert first_case[0] is not None
    assert first_case[1] is not None
    assert first_case[2] is not None
    
    conn.close()

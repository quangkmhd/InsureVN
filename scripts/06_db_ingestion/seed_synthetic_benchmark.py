import sqlite3
import os
import sys

# Ensure src module can be imported when running as script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.core.logger import get_logger

logger = get_logger("seed_synthetic_benchmark")

def seed_benchmark_cases(db_path: str, cases_count: int = 100):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # We assume schema.sql has been executed
    
    # Create a synthetic user to attach cases to
    cursor.execute("""
        INSERT OR IGNORE INTO synthetic_users (id, age, gender) 
        VALUES ('U_BENCHMARK', 30, 'Nam')
    """)
    
    # Generate exactly 100 benchmark cases
    for i in range(1, cases_count + 1):
        intent_group = "policy_qa"
        risk_level = "low"
        workflow = "policy_qa"
        
        if i % 3 == 0:
            intent_group = "claim"
            risk_level = "high"
            workflow = "high_risk_claim"
        elif i % 2 == 0:
            intent_group = "comparison"
            risk_level = "medium"
            workflow = "verified_compare"
            
        cursor.execute("""
            INSERT OR IGNORE INTO synthetic_benchmark_cases 
            (case_id, user_id, query, expected_intent_group, expected_risk_level, expected_workflow, expected_evidence_types)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            f"case_{i:03d}",
            "U_BENCHMARK",
            f"Test question {i}",
            intent_group,
            risk_level,
            workflow,
            '["sqlite_row", "qdrant_doc"]'
        ))
        
    conn.commit()
    conn.close()
    
    logger.info(
        f"Seeded {cases_count} synthetic benchmark cases",
        extra={
            "component": "synthetic_seed",
            "total_evidence_count": cases_count
        }
    )

if __name__ == "__main__":
    db_path = os.environ.get("DB_PATH", "database/insurevn.db")
    seed_benchmark_cases(db_path)
    print(f"Successfully seeded 100 benchmark cases into {db_path}")

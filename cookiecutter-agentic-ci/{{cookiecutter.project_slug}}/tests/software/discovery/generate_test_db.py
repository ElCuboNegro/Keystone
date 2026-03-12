import sqlite3
import os

def generate_mock_db(db_path="tests/software/discovery/mock_lineage.db"):
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Setup Schema
    cur.execute("""
        CREATE TABLE sql_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caller_path TEXT,
            dependency_name TEXT,
            dependency_type TEXT,
            raw_line TEXT,
            direction TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE sql_metrics (
            path TEXT PRIMARY KEY,
            line_count INTEGER,
            proc_name TEXT,
            crud_operations TEXT,
            complexity_score INTEGER
        )
    """)
    
    # 1. Standard Case: 1 Input, 1 Output
    cur.execute("INSERT INTO sql_metrics VALUES ('path/proc1.sql', 10, 'Proc1', 'CR', 5)")
    cur.execute("INSERT INTO sql_dependencies (caller_path, dependency_name, dependency_type, direction) VALUES ('path/proc1.sql', 'TableInput1', 'TABLE/VIEW', 'INPUT')")
    cur.execute("INSERT INTO sql_dependencies (caller_path, dependency_name, dependency_type, direction) VALUES ('path/proc1.sql', 'TableOutput1', 'TABLE/VIEW', 'OUTPUT')")
    
    # 2. Multi-IO Case: 2 Inputs, 2 Outputs
    cur.execute("INSERT INTO sql_metrics VALUES ('path/proc2.sql', 50, 'Proc2', 'CRUD', 20)")
    cur.execute("INSERT INTO sql_dependencies (caller_path, dependency_name, dependency_type, direction) VALUES ('path/proc2.sql', 'TableInputA', 'TABLE/VIEW', 'INPUT')")
    cur.execute("INSERT INTO sql_dependencies (caller_path, dependency_name, dependency_type, direction) VALUES ('path/proc2.sql', 'TableInputB', 'TABLE/VIEW', 'INPUT')")
    cur.execute("INSERT INTO sql_dependencies (caller_path, dependency_name, dependency_type, direction) VALUES ('path/proc2.sql', 'TableOutputA', 'TABLE/VIEW', 'OUTPUT')")
    cur.execute("INSERT INTO sql_dependencies (caller_path, dependency_name, dependency_type, direction) VALUES ('path/proc2.sql', 'TableOutputB', 'TABLE/VIEW', 'OUTPUT')")
    
    # 3. Special Characters Case
    cur.execute("INSERT INTO sql_metrics VALUES ('path/proc3.sql', 15, 'Proc3', 'R', 2)")
    cur.execute("INSERT INTO sql_dependencies (caller_path, dependency_name, dependency_type, direction) VALUES ('path/proc3.sql', '[Schema].[Table_With_Spaces]', 'TABLE/VIEW', 'INPUT')")
    
    conn.commit()
    conn.close()
    print(f"Mock database generated at {db_path}")

if __name__ == "__main__":
    generate_mock_db()

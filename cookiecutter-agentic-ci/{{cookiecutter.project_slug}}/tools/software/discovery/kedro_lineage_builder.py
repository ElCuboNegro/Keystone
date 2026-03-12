import sqlite3
import yaml
import argparse
import os
import re
from pathlib import Path

def summarize_sql(content):
    content_upper = content.upper()
    if "TRUNCATE TABLE" in content_upper and "INSERT INTO" in content_upper:
        return "Full Refresh: Clears and repopulates target table."
    if "MERGE INTO" in content_upper:
        return "Upsert: Synchronizes source and target data."
    if "INSERT INTO" in content_upper and "SELECT" in content_upper:
        return "Data Transfer: Transformation and ingestion into target table."
    return "Data Retrieval: Pure query or view definition."

class KedroLineageBuilder:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def build(self, output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
            pipeline_map = {}
            catalog = {}

            self.cursor.execute("SELECT path, proc_name FROM sql_metrics")
            rows = self.cursor.fetchall()
            proc_info = {row[1]: row[0] for row in rows}

            for proc_name, proc_path in proc_info.items():
                logic_summary = "Procedural Logic"
                try:
                    with open(proc_path, 'r', encoding='utf-8', errors='ignore') as f:
                        logic_summary = summarize_sql(f.read())
                except: pass

                if proc_name not in pipeline_map:
                    pipeline_map[proc_name] = {"inputs": set(), "outputs": set(), "summary": logic_summary}

            self.cursor.execute("SELECT caller_path, dependency_name, direction FROM sql_dependencies WHERE dependency_type = 'TABLE/VIEW'")
            for caller_path, dep_name, direction in self.cursor.fetchall():
                # reverse lookup proc_name
                p_name = next((name for name, path in proc_info.items() if path == caller_path), caller_path)
                
                if p_name not in pipeline_map:
                    pipeline_map[p_name] = {"inputs": set(), "outputs": set(), "summary": "Unknown"}

                clean_dep = dep_name.replace('[', '').replace(']', '').replace('.', '_')
                if direction == 'INPUT':
                    pipeline_map[p_name]["inputs"].add(clean_dep)
                else:
                    pipeline_map[p_name]["outputs"].add(clean_dep)
                
                catalog[clean_dep] = {
                    "type": "pandas.CSVDataset",
                    "filepath": f"data/01_raw/{clean_dep}.csv"
                }

            # Generate catalog.yml
            with open(os.path.join(output_dir, "catalog.yml"), "w") as f:
                yaml.dump(catalog, f, default_flow_style=False)

            # Generate pipeline.py
            with open(os.path.join(output_dir, "pipeline_dag.py"), "w", encoding='utf-8') as f:
                f.write("from kedro.pipeline import Pipeline, node, pipeline\n\n")
                f.write("def create_pipeline(**kwargs) -> Pipeline:\n")
                f.write("    return pipeline([\n")
                for proc, data in pipeline_map.items():
                    inputs = list(data["inputs"])
                    outputs = list(data["outputs"])
                    if not outputs: outputs = [f"{proc}_output"]
                    
                    # Extract raw SQL code for the node
                    raw_sql = ""
                    p_path = proc_info.get(proc)
                    if p_path and os.path.exists(p_path):
                        try:
                            with open(p_path, 'r', encoding='utf-8', errors='ignore') as sql_f:
                                raw_sql = sql_f.read().replace("'''", "''''") # Escape triple quotes
                        except: pass

                    f.write(f"        node(\n")
                    f.write(f"            func=lambda *x: None, # Transformation logic below\n")
                    f.write(f"            inputs={inputs},\n")
                    f.write(f"            outputs={outputs},\n")
                    f.write(f"            name='{proc}',\n")
                    f.write(f"            doc='''\nLOGIC SUMMARY: {data['summary']}\n\nSOURCE SQL:\n{raw_sql}\n'''\n")
                    f.write(f"        ),\n")
                f.write("    ])\n")
            print(f"Kedro lineage with summaries generated in {output_dir}")
        finally:
            self.conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("db", help="Path to logic database")
    parser.add_argument("--out", default="output/kedro_mapping", help="Output directory")
    args = parser.parse_args()
    
    builder = KedroLineageBuilder(args.db)
    builder.build(args.out)

import pytest
import os
import yaml
import sqlite3
from tools.software.discovery.kedro_lineage_builder import KedroLineageBuilder
from tests.software.discovery.generate_test_db import generate_mock_db

TEST_DB = "tests/software/discovery/mock_lineage.db"
TEST_OUT = "tests/software/discovery/test_output"

@pytest.fixture(scope="module", autouse=True)
def setup_test_data():
    generate_mock_db(TEST_DB)
    yield
    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_kedro_mapping_generation():
    builder = KedroLineageBuilder(TEST_DB)
    builder.build(TEST_OUT)
    
    assert os.path.exists(os.path.join(TEST_OUT, "catalog.yml"))
    assert os.path.exists(os.path.join(TEST_OUT, "pipeline_dag.py"))

def test_catalog_content():
    with open(os.path.join(TEST_OUT, "catalog.yml"), "r") as f:
        catalog = yaml.safe_load(f)
    
    # Check if special characters were cleaned
    # [Schema].[Table_With_Spaces] -> Schema_Table_With_Spaces
    assert "Schema_Table_With_Spaces" in catalog
    assert "TableInput1" in catalog
    assert "TableOutputB" in catalog

def test_pipeline_logic():
    with open(os.path.join(TEST_OUT, "pipeline_dag.py"), "r") as f:
        content = f.read()
    
    # Check for nodes
    assert "name='Proc1'" in content
    assert "name='Proc2'" in content
    assert "name='Proc3'" in content
    
    # Check wiring of Proc1
    # node(func=..., inputs=['TableInput1'], outputs=['TableOutput1'], name='Proc1')
    assert "'TableInput1'" in content
    assert "'TableOutput1'" in content
    
    # Check cleaning in pipeline
    assert "'Schema_Table_With_Spaces'" in content

if __name__ == "__main__":
    # If run directly, execute tests manually or via pytest
    import sys
    pytest.main([__file__])

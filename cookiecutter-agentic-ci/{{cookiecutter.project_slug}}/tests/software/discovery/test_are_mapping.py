import pytest
import os
import yaml
from tools.software.discovery.kedro_lineage_builder import KedroLineageBuilder

ARE_DB = "output/analysis_dbs/are_lineage.db"
ARE_OUT = "output/are_kedro_test"

@pytest.fixture(scope="module")
def run_are_builder():
    # Only run if the DB exists (it was created in previous steps)
    if not os.path.exists(ARE_DB):
        pytest.skip("ARE Lineage DB not found. Run analysis first.")
    
    builder = KedroLineageBuilder(ARE_DB)
    builder.build(ARE_OUT)
    return ARE_OUT

def test_are_catalog_registration(run_are_builder):
    with open(os.path.join(run_are_builder, "catalog.yml"), "r") as f:
        catalog = yaml.safe_load(f)
    
    # Verify core ARE datasets are registered
    # [ARESch].[AreRelConnumArticuloPrecioMin] -> ARESch_AreRelConnumArticuloPrecioMin
    assert "ARESch_AreRelConnumArticuloPrecioMin" in catalog
    assert "AreSch_VtaCTraFacturaVw" in catalog
    assert "ARESch_AreCatDireccionesDumping" in catalog

def test_are_brain_node_wiring(run_are_builder):
    with open(os.path.join(run_are_builder, "pipeline_dag.py"), "r") as f:
        content = f.read()
    
    # Verify the 'Brain' procedure exists as a node
    assert "name='[ARESch].[AreObtienePrecioMX1]'" in content
    
    # Verify specific input wiring for the brain node
    assert "'ARESch_AreRelConnumArticuloPrecioMin'" in content
    assert "'AreSch_VtaCTraFacturaVw'" in content

def test_are_orchestrator_presence(run_are_builder):
    with open(os.path.join(run_are_builder, "pipeline_dag.py"), "r") as f:
        content = f.read()
    
    # The massive orchestrator (Complexity 249) must be present
    assert "name='[Are2Sch].[AreEstudio_CU1_Pag1_ObtenerInterfaces_Proc]'" in content

if __name__ == "__main__":
    import sys
    pytest.main([__file__])

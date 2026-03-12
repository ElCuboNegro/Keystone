Feature: ARE Data Staging Interfaces
  As a Data Pipeline Engineer
  I want to synchronize source data into ARE staging tables
  In order to provide a clean, local dataset for price calculations

  Scenario Outline: Staging data via Full Refresh
    Given a staging table "<target>" exists in ARE
    And the source data is available in the production database
    When the interface procedure "<procedure>" is executed
    Then the staging table "<target>" should be truncated
    And the current production data should be copied into "<target>"

    Examples:
      | procedure                                           | target                      |
      | AreEstudio_CU1_Pag1_ObtenerInterfaces_AceTraViaje   | AreEstudioAceTraViaje       |
      | AreEstudio_CU1_Pag1_ObtenerInterfaces_ArtRelPais    | AreEstudioArtRelArticuloPais|
      | AreEstudio_CU1_Pag1_ObtenerInterfaces_VtaFactura    | AreEstudioVtaCTraFactura    |

  Scenario: Data Retrieval and Validation
    Given the Precios Mínimos logic requires "VtaTraProforma"
    When the "AreEstudio_CU1_Pag1_ObtenerInterfaces_VtaTraProforma_Proc" is called
    Then it should retrieve proforma records directly from DEAOFINET05.Ventas.VtaSch
    And ensure the data is complete before price retrieval begins

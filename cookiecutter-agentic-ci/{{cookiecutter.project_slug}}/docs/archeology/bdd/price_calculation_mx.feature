Feature: Mexico Price Retrieval (AreObtienePrecioMX1)
  As an ARE Logic Processor
  I want to determine the best available price for a given CONNUM
  In order to provide accurate data for the dumping reports

  Scenario: Applying manual invoice overrides (Logic F-010)
    Given an invoice "G373955" is listed in the #TmpCostTestManual hardcoded filter
    When the Mexico Price Retrieval logic processes the period
    Then the invoice "G373955" must be filtered out of the price calculation
    And this should be flagged as "Manual Business Override"

  Scenario: Falling back to similar products via CONNUM distance (Logic F-011)
    Given I am searching for the price of CONNUM "242222"
    And no direct sales exist for CONNUM "242222" in the current period
    When the system executes the equivalency loop
    Then it should find the most similar CONNUM using [ARESch].[AreDiferenciaConnumrFn]
    And use that similar product's price as the fallback
    And return the fallback CONNUM ID in the output parameter @psConnumPrecio

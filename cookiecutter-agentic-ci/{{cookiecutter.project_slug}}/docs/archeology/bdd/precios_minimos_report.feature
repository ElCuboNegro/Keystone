Feature: Precios Mínimos General Report
  As an Analyst for Regulatory Affairs (ARE)
  I want to generate a report comparing USA and Mexico prices
  In order to identify dumping risks and comply with US authorities

  Background:
    Given the system has established a connection to DEAOFINET15 (ARE_PROD)
    And the data interfaces have been officially synchronized

  Scenario: Excluding invoices with high credit note volume (Quality Rule F-007)
    Given an invoice "INV-USA-001" has an original amount of 1000 USD
    And it has associated Credit Notes totaling 985 USD
    When the Precios Mínimos report is generated
    Then the invoice "INV-USA-001" should be excluded from the calculation
    And the reason should be "Credit Notes exceed 98% of invoice amount"

  Scenario: Reconciling USA and Mexico transactions via Mirror Invoices (Logic F-009)
    Given an invoice exists in the USA system with ID "FactUSA_123"
    And a matching invoice exists in the Mexico system with ID "FactMEX_456"
    And they are linked in the [AreSch].[VtaRelFabricacionEspejoVw] mapping
    When the report performs the transaction reconciliation
    Then the logic must join both records into a single row in #tblResultadoFinal
    And use the Mexico price for the dumping comparison

  Scenario: Normalizing amounts to USD based on transaction date (Logic F-012)
    Given a Mexico invoice "FactMEX_789" with an amount of 20,000 MXN
    And the invoice date is "2024-01-15"
    And the exchange rate for "2024-01-15" in [AreSch].[ConCatParidadVw] is 17.0 MXN/USD
    When the price calculation is executed
    Then the amount should be recorded as 1,176.47 USD

-- =============================================================================
-- LoadStar Freight Intelligence
-- 04: Streaming Pipeline
-- JSON staging table, change stream, flattened view, and simulation task
-- Proves: "Your legacy DB stays untouched while Snowflake ingests in real-time"
-- =============================================================================

USE DATABASE FREIGHT_DEMO;
USE SCHEMA RAW;

-- Stream on JSON staging table (change data capture)
CREATE OR REPLACE STREAM INVOICE_JSON_STREAM
    ON TABLE INVOICE_TRANSACTIONS_JSON
    COMMENT = 'CDC stream on JSON staging table for real-time invoice ingestion';

-- Flattened view: typed extraction from JSON VARIANT
CREATE OR REPLACE VIEW INVOICE_TRANSACTIONS_FLATTENED AS
SELECT 
    RAW_DATA:invoice_id::TEXT AS INVOICE_ID,
    RAW_DATA:broker_id::NUMBER AS BROKER_ID,
    RAW_DATA:carrier_id::NUMBER AS CARRIER_ID,
    RAW_DATA:invoice_amount::NUMBER AS INVOICE_AMOUNT,
    RAW_DATA:factoring_fee_pct::NUMBER AS FACTORING_FEE_PCT,
    RAW_DATA:invoice_date::DATE AS INVOICE_DATE,
    RAW_DATA:factored_date::DATE AS FACTORED_DATE,
    RAW_DATA:payment_received_date::DATE AS PAYMENT_RECEIVED_DATE,
    RAW_DATA:origin_city::TEXT AS ORIGIN_CITY,
    RAW_DATA:destination_city::TEXT AS DESTINATION_CITY,
    RAW_DATA:miles::NUMBER AS MILES,
    RAW_DATA:status::TEXT AS STATUS,
    RAW_DATA:equipment_type::TEXT AS EQUIPMENT_TYPE,
    RAW_DATA:funding_method::TEXT AS FUNDING_METHOD,
    INGESTED_AT
FROM FREIGHT_DEMO.RAW.INVOICE_TRANSACTIONS_JSON;

-- Simulation task: inserts 5 synthetic JSON rows per minute
-- Simulates Snowpipe Streaming from a real-time source
CREATE OR REPLACE TASK SIMULATE_STREAMING_INGESTION
    WAREHOUSE = ANALYTICS_WH
    SCHEDULE = '1 MINUTE'
    COMMENT = 'Simulates Snowpipe Streaming - inserts synthetic JSON invoices every 60s'
AS
INSERT INTO FREIGHT_DEMO.RAW.INVOICE_TRANSACTIONS_JSON (RAW_DATA)
SELECT OBJECT_CONSTRUCT(
    'invoice_id', 'INV-STREAM-' || TO_VARCHAR(UNIFORM(100000, 999999, RANDOM())),
    'broker_id', UNIFORM(1, 200, RANDOM()),
    'carrier_id', UNIFORM(1, 500, RANDOM()),
    'invoice_amount', UNIFORM(500, 15000, RANDOM()),
    'factoring_fee_pct', UNIFORM(1, 5, RANDOM()),
    'invoice_date', DATEADD('day', -UNIFORM(1, 30, RANDOM()), CURRENT_DATE()),
    'factored_date', DATEADD('day', -UNIFORM(1, 15, RANDOM()), CURRENT_DATE()),
    'payment_received_date', NULL,
    'origin_city', 'Dallas, TX',
    'destination_city', 'Houston, TX',
    'miles', UNIFORM(100, 3000, RANDOM()),
    'status', 'PENDING',
    'equipment_type', 'Dry Van',
    'funding_method', 'Same-Day'
) FROM TABLE(GENERATOR(ROWCOUNT => 5));

-- Start the streaming simulation
ALTER TASK SIMULATE_STREAMING_INGESTION RESUME;

-- Grant Ops role access to monitor streaming
GRANT SELECT ON TABLE FREIGHT_DEMO.RAW.INVOICE_TRANSACTIONS_JSON TO ROLE FREIGHT_OPS;

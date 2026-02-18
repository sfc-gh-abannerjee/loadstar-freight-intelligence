-- =============================================================================
-- LoadStar Freight Intelligence
-- 02: Generate Synthetic Data
-- =============================================================================
-- This file contains the data generation logic for the demo.
-- It uses Snowflake's GENERATOR and UNIFORM/RANDOM functions to create
-- realistic freight factoring data.
--
-- Row counts: 200 brokers, 500 carriers, 10K invoices, 5K loads, 27K weather
-- Weather data should ideally come from Snowflake Marketplace (Weather Source).
-- The INSERT below creates minimal weather data for standalone testing.
-- =============================================================================

USE DATABASE FREIGHT_DEMO;
USE SCHEMA RAW;

-- ============================================================
-- Broker Profiles (200 rows)
-- ============================================================
INSERT INTO BROKER_PROFILES
SELECT
    ROW_NUMBER() OVER (ORDER BY SEQ4()) AS BROKER_ID,
    'MC-' || LPAD(UNIFORM(100000, 999999, RANDOM())::TEXT, 6, '0') AS MC_NUMBER,
    'Broker_' || LPAD(ROW_NUMBER() OVER (ORDER BY SEQ4())::TEXT, 3, '0') AS BROKER_NAME,
    UNIFORM(350, 850, RANDOM()) AS CREDIT_SCORE,
    UNIFORM(1, 5, RANDOM()) AS FACTORING_RATE_PCT,
    CASE WHEN UNIFORM(1, 2, RANDOM()) = 1 THEN 'RECOURSE' ELSE 'NON_RECOURSE' END AS FACTORING_TYPE,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'TX' WHEN 2 THEN 'CA' WHEN 3 THEN 'FL' WHEN 4 THEN 'IL' ELSE 'GA'
    END AS HQ_STATE,
    DATEADD('day', -UNIFORM(365, 2555, RANDOM()), CURRENT_DATE()) AS RELATIONSHIP_START,
    UNIFORM(50000, 5000000, RANDOM()) AS TOTAL_FACTORED_VOLUME,
    CASE WHEN UNIFORM(1, 20, RANDOM()) = 1 THEN TRUE ELSE FALSE END AS DOUBLE_BROKER_FLAG,
    UNIFORM(0, 10, RANDOM()) AS DISPUTE_COUNT,
    CASE WHEN UNIFORM(1, 10, RANDOM()) <= 8 THEN 'ACTIVE' ELSE 'SUSPENDED' END AS STATUS
FROM TABLE(GENERATOR(ROWCOUNT => 200));

-- ============================================================
-- Carrier Profiles (500 rows)
-- ============================================================
INSERT INTO CARRIER_PROFILES
SELECT
    ROW_NUMBER() OVER (ORDER BY SEQ4()) AS CARRIER_ID,
    'MC-' || LPAD(UNIFORM(100000, 999999, RANDOM())::TEXT, 6, '0') AS MC_NUMBER,
    'Carrier_' || LPAD(ROW_NUMBER() OVER (ORDER BY SEQ4())::TEXT, 3, '0') AS CARRIER_NAME,
    CASE UNIFORM(1, 4, RANDOM())
        WHEN 1 THEN 'Dry Van' WHEN 2 THEN 'Reefer' WHEN 3 THEN 'Flatbed' ELSE 'Tanker'
    END AS EQUIPMENT_TYPE,
    UNIFORM(1, 50, RANDOM()) AS FLEET_SIZE,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'TX' WHEN 2 THEN 'CA' WHEN 3 THEN 'FL' WHEN 4 THEN 'IL' ELSE 'OH'
    END AS HOME_STATE,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'Dallas' WHEN 2 THEN 'Houston' WHEN 3 THEN 'Austin' WHEN 4 THEN 'Chicago' ELSE 'Miami'
    END AS HOME_CITY,
    UNIFORM(-100, -80, RANDOM()) AS HOME_LONGITUDE,
    UNIFORM(25, 45, RANDOM()) AS HOME_LATITUDE,
    DATEADD('day', -UNIFORM(30, 1825, RANDOM()), CURRENT_DATE()) AS ONBOARDED_DATE,
    CASE WHEN UNIFORM(1, 10, RANDOM()) <= 9 THEN 'ACTIVE' ELSE 'INACTIVE' END AS STATUS,
    -- PII fields (will be masked via governance policies)
    LPAD(UNIFORM(100, 999, RANDOM())::TEXT, 3, '0') || '-' ||
    LPAD(UNIFORM(10, 99, RANDOM())::TEXT, 2, '0') || '-' ||
    LPAD(UNIFORM(1000, 9999, RANDOM())::TEXT, 4, '0') AS DRIVER_SSN,
    LPAD(UNIFORM(1000000000, 9999999999, RANDOM())::TEXT, 10, '0') AS BANK_ACCOUNT_NUMBER
FROM TABLE(GENERATOR(ROWCOUNT => 500));

-- ============================================================
-- Invoice Transactions (10,000 rows)
-- ============================================================
INSERT INTO INVOICE_TRANSACTIONS
SELECT
    'INV-' || LPAD(ROW_NUMBER() OVER (ORDER BY SEQ4())::TEXT, 7, '0') AS INVOICE_ID,
    UNIFORM(1, 200, RANDOM()) AS BROKER_ID,
    UNIFORM(1, 500, RANDOM()) AS CARRIER_ID,
    UNIFORM(500, 25000, RANDOM()) AS INVOICE_AMOUNT,
    UNIFORM(1, 5, RANDOM()) AS FACTORING_FEE_PCT,
    DATEADD('day', -UNIFORM(1, 365, RANDOM()), CURRENT_DATE()) AS INVOICE_DATE,
    DATEADD('day', -UNIFORM(1, 350, RANDOM()), CURRENT_DATE()) AS FACTORED_DATE,
    CASE WHEN UNIFORM(1, 10, RANDOM()) <= 8
        THEN DATEADD('day', -UNIFORM(1, 300, RANDOM()), CURRENT_DATE())
        ELSE NULL
    END AS PAYMENT_RECEIVED_DATE,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'Dallas, TX' WHEN 2 THEN 'Houston, TX' WHEN 3 THEN 'Austin, TX'
        WHEN 4 THEN 'San Antonio, TX' ELSE 'El Paso, TX'
    END AS ORIGIN_CITY,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'Chicago, IL' WHEN 2 THEN 'Miami, FL' WHEN 3 THEN 'Atlanta, GA'
        WHEN 4 THEN 'Los Angeles, CA' ELSE 'New York, NY'
    END AS DESTINATION_CITY,
    UNIFORM(100, 3000, RANDOM()) AS MILES,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'PAID' WHEN 2 THEN 'PAID' WHEN 3 THEN 'PAID'
        WHEN 4 THEN 'PENDING' ELSE 'DISPUTED'
    END AS STATUS,
    CASE UNIFORM(1, 4, RANDOM())
        WHEN 1 THEN 'Dry Van' WHEN 2 THEN 'Reefer' WHEN 3 THEN 'Flatbed' ELSE 'Tanker'
    END AS EQUIPMENT_TYPE,
    CASE UNIFORM(1, 3, RANDOM())
        WHEN 1 THEN 'Same-Day' WHEN 2 THEN 'Next-Day' ELSE 'Standard'
    END AS FUNDING_METHOD
FROM TABLE(GENERATOR(ROWCOUNT => 10000));

-- ============================================================
-- Load Postings (5,000 rows)
-- ============================================================
INSERT INTO LOAD_POSTINGS
SELECT
    'LOAD-' || LPAD(ROW_NUMBER() OVER (ORDER BY SEQ4())::TEXT, 7, '0') AS LOAD_ID,
    UNIFORM(1, 200, RANDOM()) AS BROKER_ID,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'Dallas' WHEN 2 THEN 'Houston' WHEN 3 THEN 'Austin'
        WHEN 4 THEN 'San Antonio' ELSE 'El Paso'
    END AS ORIGIN_CITY,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'Texas' WHEN 2 THEN 'Texas' WHEN 3 THEN 'Texas'
        WHEN 4 THEN 'California' ELSE 'Florida'
    END AS ORIGIN_STATE,
    -- Texas-area coordinates for H3 geospatial
    UNIFORM(-106, -94, RANDOM()) AS ORIGIN_LONGITUDE,
    UNIFORM(26, 36, RANDOM()) AS ORIGIN_LATITUDE,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'Chicago' WHEN 2 THEN 'Miami' WHEN 3 THEN 'Atlanta'
        WHEN 4 THEN 'Los Angeles' ELSE 'New York'
    END AS DESTINATION_CITY,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'Illinois' WHEN 2 THEN 'Florida' WHEN 3 THEN 'Georgia'
        WHEN 4 THEN 'California' ELSE 'New York'
    END AS DESTINATION_STATE,
    UNIFORM(200, 3000, RANDOM()) AS MILES,
    UNIFORM(1, 5, RANDOM()) AS RATE_PER_MILE,
    UNIFORM(500, 15000, RANDOM()) AS TOTAL_RATE,
    CASE UNIFORM(1, 4, RANDOM())
        WHEN 1 THEN 'Dry Van' WHEN 2 THEN 'Reefer' WHEN 3 THEN 'Flatbed' ELSE 'Tanker'
    END AS EQUIPMENT_REQUIRED,
    UNIFORM(5000, 45000, RANDOM()) AS WEIGHT_LBS,
    DATEADD('hour', -UNIFORM(1, 720, RANDOM()), CURRENT_TIMESTAMP()) AS PICKUP_DATE,
    DATEADD('hour', -UNIFORM(1, 700, RANDOM()), CURRENT_TIMESTAMP()) AS DELIVERY_DATE,
    CASE WHEN UNIFORM(1, 3, RANDOM()) = 1 THEN 'OPEN' ELSE 'ASSIGNED' END AS STATUS,
    DATEADD('hour', -UNIFORM(1, 740, RANDOM()), CURRENT_TIMESTAMP()) AS POSTED_AT,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'TX' WHEN 2 THEN 'TX' WHEN 3 THEN 'TX'
        WHEN 4 THEN 'CA' ELSE 'FL'
    END AS ORIGIN_STATE_CODE
FROM TABLE(GENERATOR(ROWCOUNT => 5000));

-- ============================================================
-- Texas Weather (minimal sample -- use Snowflake Marketplace for production)
-- In production, subscribe to Weather Source on Snowflake Marketplace
-- and join by city/date for real-time weather risk.
-- ============================================================
INSERT INTO TEXAS_WEATHER
SELECT
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN 'Dallas' WHEN 2 THEN 'Houston' WHEN 3 THEN 'Austin'
        WHEN 4 THEN 'San Antonio' ELSE 'El Paso'
    END AS CITY_NAME,
    CASE UNIFORM(1, 5, RANDOM())
        WHEN 1 THEN '75201' WHEN 2 THEN '77001' WHEN 3 THEN '73301'
        WHEN 4 THEN '78201' ELSE '79901'
    END AS POSTAL_CODE,
    DATEADD('day', -SEQ4(), CURRENT_DATE()) AS DATE_VALID_STD,
    ROUND(UNIFORM(32, 105, RANDOM()) + UNIFORM(0, 9, RANDOM()) / 10.0, 1) AS AVG_TEMP_F,
    ROUND(UNIFORM(0, 60, RANDOM()) + UNIFORM(0, 9, RANDOM()) / 10.0, 1) AS MAX_WIND_MPH,
    ROUND(UNIFORM(0, 300, RANDOM()) / 100.0, 2) AS PRECIPITATION_IN,
    0.00 AS SNOWFALL_IN,
    UNIFORM(0, 100, RANDOM()) AS CLOUD_COVER_PCT,
    CASE
        WHEN UNIFORM(0, 60, RANDOM()) > 40 THEN 'HIGH'
        WHEN UNIFORM(0, 60, RANDOM()) > 20 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS WEATHER_RISK_LEVEL
FROM TABLE(GENERATOR(ROWCOUNT => 500));

-- ============================================================
-- Zero-Copy Clone for DS Sandbox
-- ============================================================
CREATE SCHEMA IF NOT EXISTS FREIGHT_DEMO.DS_SANDBOX
    COMMENT = 'Data science sandbox - zero-copy clone of RAW (no storage cost)';

CREATE OR REPLACE TABLE FREIGHT_DEMO.DS_SANDBOX.BROKER_PROFILES CLONE FREIGHT_DEMO.RAW.BROKER_PROFILES;
CREATE OR REPLACE TABLE FREIGHT_DEMO.DS_SANDBOX.CARRIER_PROFILES CLONE FREIGHT_DEMO.RAW.CARRIER_PROFILES;
CREATE OR REPLACE TABLE FREIGHT_DEMO.DS_SANDBOX.INVOICE_TRANSACTIONS CLONE FREIGHT_DEMO.RAW.INVOICE_TRANSACTIONS;
CREATE OR REPLACE TABLE FREIGHT_DEMO.DS_SANDBOX.LOAD_POSTINGS CLONE FREIGHT_DEMO.RAW.LOAD_POSTINGS;
CREATE OR REPLACE TABLE FREIGHT_DEMO.DS_SANDBOX.TEXAS_WEATHER CLONE FREIGHT_DEMO.RAW.TEXAS_WEATHER;

-- Grant DS role access to sandbox tables
GRANT SELECT ON ALL TABLES IN SCHEMA FREIGHT_DEMO.DS_SANDBOX TO ROLE FREIGHT_DATA_SCIENTIST;

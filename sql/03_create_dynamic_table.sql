-- =============================================================================
-- LoadStar Freight Intelligence
-- 03: Dynamic Table - BROKER_360 (The "Golden Record")
-- Single row per broker combining payment history, credit, fraud risk,
-- weather, and geospatial lane density. Auto-refreshes every 5 minutes.
-- =============================================================================

USE DATABASE FREIGHT_DEMO;
USE SCHEMA ANALYTICS;

CREATE OR REPLACE DYNAMIC TABLE BROKER_360
    TARGET_LAG = '5 minutes'
    WAREHOUSE = ANALYTICS_WH
    COMMENT = 'The Broker Object - Single Source of Truth combining payment history, credit, fraud risk, weather, and geospatial lane density'
AS
WITH broker_payment_metrics AS (
    SELECT 
        broker_id,
        COUNT(*) AS total_invoices,
        SUM(invoice_amount) AS total_factored_amount,
        AVG(invoice_amount) AS avg_invoice_amount,
        AVG(DATEDIFF('day', invoice_date, payment_received_date)) AS avg_days_to_pay,
        COUNT(CASE WHEN DATEDIFF('day', invoice_date, payment_received_date) > 45 THEN 1 END) AS late_payment_count,
        COUNT(CASE WHEN status = 'DISPUTED' THEN 1 END) AS disputed_invoices,
        SUM(CASE WHEN payment_received_date IS NULL THEN invoice_amount ELSE 0 END) AS outstanding_amount
    FROM FREIGHT_DEMO.RAW.INVOICE_TRANSACTIONS
    GROUP BY broker_id
),
lane_analysis AS (
    SELECT 
        broker_id,
        COUNT(DISTINCT origin_city || '-' || destination_city) AS unique_lanes,
        MODE(origin_city) AS primary_origin,
        MODE(destination_city) AS primary_destination,
        AVG(miles) AS avg_haul_miles
    FROM FREIGHT_DEMO.RAW.INVOICE_TRANSACTIONS
    GROUP BY broker_id
),
geo_lane_density AS (
    SELECT 
        broker_id,
        COUNT(DISTINCT H3_LATLNG_TO_CELL(origin_latitude, origin_longitude, 4)) AS origin_h3_cells,
        COUNT(DISTINCT H3_LATLNG_TO_CELL(origin_latitude, origin_longitude, 4) || '-' || 
              COALESCE(destination_state::TEXT, 'UNK')) AS lane_density
    FROM FREIGHT_DEMO.RAW.LOAD_POSTINGS
    WHERE origin_latitude IS NOT NULL AND origin_longitude IS NOT NULL
    GROUP BY broker_id
),
latest_weather AS (
    SELECT 
        CITY_NAME,
        weather_risk_level,
        avg_temp_f,
        max_wind_mph,
        precipitation_in
    FROM FREIGHT_DEMO.RAW.TEXAS_WEATHER
    QUALIFY ROW_NUMBER() OVER (PARTITION BY CITY_NAME ORDER BY DATE_VALID_STD DESC) = 1
)
SELECT 
    b.broker_id,
    b.broker_name,
    b.mc_number,
    b.hq_state,
    b.credit_score,
    b.factoring_type,
    b.factoring_rate_pct,
    b.relationship_start,
    b.status AS broker_status,
    
    -- Payment metrics
    COALESCE(pm.total_invoices, 0) AS total_invoices,
    COALESCE(pm.total_factored_amount, 0) AS total_factored_amount,
    ROUND(COALESCE(pm.avg_invoice_amount, 0), 2) AS avg_invoice_amount,
    ROUND(COALESCE(pm.avg_days_to_pay, 0), 1) AS avg_days_to_pay,
    COALESCE(pm.late_payment_count, 0) AS late_payment_count,
    COALESCE(pm.disputed_invoices, 0) AS disputed_invoices,
    COALESCE(pm.outstanding_amount, 0) AS outstanding_amount,
    
    -- Lane analysis
    COALESCE(la.unique_lanes, 0) AS unique_lanes,
    la.primary_origin,
    la.primary_destination,
    ROUND(COALESCE(la.avg_haul_miles, 0), 0) AS avg_haul_miles,
    
    -- Geospatial lane density (H3 resolution 4 cells)
    COALESCE(gld.lane_density, 0) AS lane_density,
    COALESCE(gld.origin_h3_cells, 0) AS origin_h3_cells,
    
    -- Fraud signals
    b.double_broker_flag,
    b.dispute_count,
    CASE 
        WHEN b.double_broker_flag = TRUE THEN 'CRITICAL'
        WHEN b.dispute_count >= 5 OR COALESCE(pm.disputed_invoices, 0) >= 3 THEN 'HIGH'
        WHEN b.credit_score < 500 OR COALESCE(pm.avg_days_to_pay, 0) > 60 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS fraud_risk_level,
    
    -- Weather risk
    w.weather_risk_level AS current_weather_risk,
    w.avg_temp_f AS origin_temp_f,
    w.max_wind_mph AS origin_wind_mph,
    
    -- Composite risk score (0-100, higher = riskier)
    ROUND(
        (CASE WHEN b.credit_score < 400 THEN 40 
              WHEN b.credit_score < 550 THEN 25 
              WHEN b.credit_score < 700 THEN 10 
              ELSE 0 END) +
        (CASE WHEN COALESCE(pm.avg_days_to_pay, 0) > 60 THEN 25 
              WHEN COALESCE(pm.avg_days_to_pay, 0) > 45 THEN 15 
              ELSE 0 END) +
        (CASE WHEN b.double_broker_flag THEN 30 ELSE 0 END) +
        (CASE WHEN w.weather_risk_level = 'HIGH' THEN 10 
              WHEN w.weather_risk_level = 'MEDIUM' THEN 5 
              ELSE 0 END)
    , 0) AS composite_risk_score,
    
    CURRENT_TIMESTAMP() AS last_refreshed

FROM FREIGHT_DEMO.RAW.BROKER_PROFILES b
LEFT JOIN broker_payment_metrics pm ON b.broker_id = pm.broker_id
LEFT JOIN lane_analysis la ON b.broker_id = la.broker_id
LEFT JOIN geo_lane_density gld ON b.broker_id = gld.broker_id
LEFT JOIN latest_weather w ON SPLIT_PART(la.primary_origin, ',', 1) = w.CITY_NAME;

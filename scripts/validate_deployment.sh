#!/bin/bash
# =============================================================================
# LoadStar Freight Intelligence - Deployment Validator
# Runs verification queries to confirm all objects are deployed correctly
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="$PROJECT_DIR/config/demo_config.env"
source "$CONFIG"

CONN="${SNOW_CONNECTION:-default}"
PASS=0
FAIL=0

check() {
    local desc="$1"
    local sql="$2"
    local expected="$3"
    
    result=$(snow sql -c "$CONN" -q "$sql" --format csv 2>/dev/null | tail -1 || echo "ERROR")
    
    if [[ "$result" == *"$expected"* ]]; then
        echo "  PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc (got: $result, expected: $expected)"
        FAIL=$((FAIL + 1))
    fi
}

echo "==========================================="
echo "  LoadStar Freight Intelligence - Validate"
echo "==========================================="
echo ""

echo "RAW Tables:"
check "broker_profiles (200 rows)" \
    "SELECT COUNT(*) FROM ${DATABASE}.RAW.BROKER_PROFILES" "200"
check "carrier_profiles (500 rows)" \
    "SELECT COUNT(*) FROM ${DATABASE}.RAW.CARRIER_PROFILES" "500"
check "invoice_transactions (10000 rows)" \
    "SELECT COUNT(*) FROM ${DATABASE}.RAW.INVOICE_TRANSACTIONS" "10000"
check "load_postings (5000 rows)" \
    "SELECT COUNT(*) FROM ${DATABASE}.RAW.LOAD_POSTINGS" "5000"
check "texas_weather has data" \
    "SELECT CASE WHEN COUNT(*) > 0 THEN 'HAS_DATA' ELSE 'EMPTY' END FROM ${DATABASE}.RAW.TEXAS_WEATHER" "HAS_DATA"

echo ""
echo "Analytics Layer:"
check "BROKER_360 dynamic table (200 rows)" \
    "SELECT COUNT(*) FROM ${DATABASE}.ANALYTICS.BROKER_360" "200"
check "Semantic view exists" \
    "SELECT COUNT(*) FROM (SHOW SEMANTIC VIEWS IN SCHEMA ${DATABASE}.ANALYTICS)" "1"
check "Agent exists" \
    "SELECT COUNT(*) FROM (SHOW AGENTS IN SCHEMA ${DATABASE}.ANALYTICS)" "1"

echo ""
echo "ML Layer:"
check "UDF returns valid score" \
    "SELECT CASE WHEN ${DATABASE}.ML.GET_RECOMMENDATION_SCORE(1, 1) > 0 THEN 'VALID' ELSE 'ZERO' END" "VALID"
check "Recommendations table populated" \
    "SELECT CASE WHEN COUNT(*) >= 1000 THEN 'POPULATED' ELSE 'UNDERPOPULATED' END FROM ${DATABASE}.ML.CARRIERMATCH_RECOMMENDATIONS" "POPULATED"

echo ""
echo "Streaming Pipeline:"
check "JSON table exists and growing" \
    "SELECT CASE WHEN COUNT(*) > 0 THEN 'GROWING' ELSE 'EMPTY' END FROM ${DATABASE}.RAW.INVOICE_TRANSACTIONS_JSON" "GROWING"
check "Task is running" \
    "SELECT STATE FROM (SHOW TASKS IN SCHEMA ${DATABASE}.RAW) WHERE \"name\" = 'SIMULATE_STREAMING_INGESTION'" "started"

echo ""
echo "Governance:"
check "Masking policy on SSN" \
    "SELECT CASE WHEN COUNT(*) > 0 THEN 'MASKED' ELSE 'NOT_MASKED' END FROM (SHOW MASKING POLICIES IN SCHEMA ${DATABASE}.RAW)" "MASKED"

echo ""
echo "DS Sandbox:"
check "Clone exists" \
    "SELECT COUNT(*) FROM ${DATABASE}.DS_SANDBOX.INVOICE_TRANSACTIONS" "10000"

echo ""
echo "==========================================="
echo "  Results: $PASS passed, $FAIL failed"
echo "==========================================="

if [ $FAIL -gt 0 ]; then
    exit 1
fi

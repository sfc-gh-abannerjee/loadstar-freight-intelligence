#!/bin/bash
# =============================================================================
# LoadStar Freight Intelligence - One-Command Deployment
# Deploys all demo objects to a Snowflake account
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SQL_DIR="$PROJECT_DIR/sql"
CONFIG="$PROJECT_DIR/config/demo_config.env"

# Load configuration
if [ ! -f "$CONFIG" ]; then
    echo "ERROR: Config file not found at $CONFIG"
    echo "Create config/demo_config.env with your environment settings before deploying."
    exit 1
fi
source "$CONFIG"

CONN="${SNOW_CONNECTION:-default}"
echo "==========================================="
echo "  LoadStar Freight Intelligence - Deploy"
echo "==========================================="
echo "Connection: $CONN"
echo "Database:   $DATABASE"
echo "GPU Tier:   $GPU_TIER"
echo ""

run_sql() {
    local file="$1"
    local desc="$2"
    echo -n "  [$desc] Running $(basename "$file")... "
    if snow sql -c "$CONN" -f "$file" > /dev/null 2>&1; then
        echo "OK"
    else
        echo "FAILED"
        echo "  Re-running with output for debugging:"
        snow sql -c "$CONN" -f "$file"
        exit 1
    fi
}

echo "Phase 1: Infrastructure"
run_sql "$SQL_DIR/00_setup_infrastructure.sql" "infra"

echo "Phase 2: Raw Tables & Data"
run_sql "$SQL_DIR/01_create_raw_tables.sql" "tables"
run_sql "$SQL_DIR/02_generate_synthetic_data.sql" "data"

echo "Phase 3: Analytics Layer"
run_sql "$SQL_DIR/03_create_dynamic_table.sql" "broker_360"

echo "Phase 4: Streaming Pipeline"
run_sql "$SQL_DIR/04_create_streaming_pipeline.sql" "streaming"

echo "Phase 5: Governance"
run_sql "$SQL_DIR/05_create_governance.sql" "governance"

echo "Phase 6: ML Layer"
run_sql "$SQL_DIR/06_create_udf_and_sproc.sql" "udf+sproc"

echo "Phase 7: Semantic View & Agent"
run_sql "$SQL_DIR/07_create_semantic_view.sql" "semantic_view"
run_sql "$SQL_DIR/08_create_agent.sql" "agent"

echo "Phase 8: Populate Recommendations"
echo "  (This calls the UDF per row - may take 2-3 minutes)"
run_sql "$SQL_DIR/09_populate_recommendations.sql" "recommendations"

echo "Phase 9: Git Integration"
run_sql "$SQL_DIR/10_create_git_integration.sql" "git"

echo ""
echo "==========================================="
echo "  Deployment complete!"
echo "==========================================="
echo ""
echo "Next steps:"
echo "  1. Upload notebook:  ./scripts/upload_notebook.sh"
echo "  2. Register model:   python register_model.py"
echo "  3. Validate:         ./scripts/validate_deployment.sh"
echo "  4. Open Snowsight and navigate to $DATABASE.ANALYTICS"

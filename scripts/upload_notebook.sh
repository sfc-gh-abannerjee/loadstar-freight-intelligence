#!/bin/bash
# =============================================================================
# LoadStar Freight Intelligence - Notebook Upload
# Uploads notebook to Snowflake stage and creates notebook with GPU runtime
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="$PROJECT_DIR/config/demo_config.env"
source "$CONFIG"

CONN="${SNOW_CONNECTION:-default}"
NOTEBOOK_FILE="$PROJECT_DIR/notebooks/freight_360_demo.ipynb"

if [ ! -f "$NOTEBOOK_FILE" ]; then
    echo "ERROR: Notebook not found at $NOTEBOOK_FILE"
    exit 1
fi

echo "Uploading notebook to Snowflake..."

# Create internal stage for notebook
snow sql -c "$CONN" -q "CREATE STAGE IF NOT EXISTS ${DATABASE}.${ANALYTICS_SCHEMA}.NOTEBOOK_STAGE;"

# PUT notebook to stage
snow sql -c "$CONN" -q "PUT 'file://${NOTEBOOK_FILE}' @${DATABASE}.${ANALYTICS_SCHEMA}.NOTEBOOK_STAGE/ AUTO_COMPRESS=FALSE OVERWRITE=TRUE;"

# Create notebook with Container Runtime (GPU)
snow sql -c "$CONN" -q "
CREATE OR REPLACE NOTEBOOK ${DATABASE}.${ANALYTICS_SCHEMA}.${NOTEBOOK_NAME}
    FROM '@${DATABASE}.${ANALYTICS_SCHEMA}.NOTEBOOK_STAGE'
    MAIN_FILE = 'freight_360_demo.ipynb'
    COMPUTE_POOL = '${GPU_POOL}'
    RUNTIME_NAME = 'SYSTEM\$GPU_RUNTIME'
    COMMENT = 'LoadStar Freight Intelligence - 5-phase demo notebook with GPU runtime';
"

# Add live version
snow sql -c "$CONN" -q "ALTER NOTEBOOK ${DATABASE}.${ANALYTICS_SCHEMA}.${NOTEBOOK_NAME} ADD LIVE VERSION FROM LAST;"

echo "Notebook uploaded and live version created."
echo "Open in Snowsight: ${DATABASE}.${ANALYTICS_SCHEMA}.${NOTEBOOK_NAME}"

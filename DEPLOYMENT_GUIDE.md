# Deployment Guide

## Prerequisites

- Snowflake account with `ACCOUNTADMIN` role (or a role with CREATE DATABASE, CREATE WAREHOUSE, CREATE COMPUTE POOL privileges)
- [Snowflake CLI (`snow`)](https://docs.snowflake.com/en/developer-guide/snowflake-cli) installed and configured
- Python 3.10+ with `snowflake-ml-python` (for model registration only)
- ~15 minutes for full deployment

## Step 1: Configure

```bash
# Copy and edit the configuration
cp config/demo_config.env config/my_config.env
```

Edit `config/demo_config.env` with your values:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DATABASE` | `FREIGHT_DEMO` | Target database name |
| `ANALYTICS_WH` | `ANALYTICS_WH` | Analytics warehouse name |
| `DS_WH` | `DS_SANDBOX_WH` | Data science sandbox warehouse |
| `GPU_POOL` | `GPU_POOL` | Compute pool for GPU notebooks |
| `GPU_TIER` | `GPU_NV_S` | GPU instance family (`GPU_NV_S` or `GPU_NV_M`) |
| `SNOW_CONNECTION` | `default` | Snowflake CLI connection name |
| `GIT_ORIGIN` | (repo URL) | Git repo URL for Snowflake integration |

## Step 2: Deploy

```bash
source config/demo_config.env
./scripts/deploy.sh
```

This runs SQL files 00-10 in order:
1. Creates database, schemas, warehouses, compute pool, roles
2. Creates raw tables and generates synthetic data
3. Creates the BROKER_360 Dynamic Table (golden record)
4. Sets up streaming pipeline (JSON + task)
5. Applies governance (tags, masking policies, RBAC)
6. Creates scoring UDF and stored procedure
7. Creates Semantic View and Cortex Agent
8. Populates recommendation scores (~2-3 minutes)
9. Creates Git Repository integration

## Step 3: Upload Notebook (Optional)

```bash
./scripts/upload_notebook.sh
```

This uploads the demo notebook with GPU Container Runtime.

**Note:** The compute pool must be running for the notebook to execute. First-time GPU provisioning may take several minutes.

## Step 4: Register ML Model (Optional)

```bash
pip install snowflake-ml-python torch
python register_model.py
```

This trains a PyTorch `BrokerRiskNet` model and registers it in the Snowflake Model Registry.

## Step 5: Validate

```bash
./scripts/validate_deployment.sh
```

Expected output: all checks pass (RAW tables, Dynamic Table, Agent, UDF, streaming, governance, sandbox).

## Step 6: GPU Upgrade (Demo Day Only)

The default GPU tier is `GPU_NV_S` (cost-effective for development). For production demos:

```sql
ALTER COMPUTE POOL GPU_POOL SET INSTANCE_FAMILY = 'GPU_NV_M';
```

**Note:** GPU_NV_M costs ~4x more credits than GPU_NV_S. Upgrade only when ready to demo.

## Teardown

```bash
snow sql -c $SNOW_CONNECTION -f sql/99_teardown.sql
```

This removes all objects in reverse dependency order, including the database itself.

## Troubleshooting

See `docs/troubleshooting.md` for common issues including:
- UDF correlated subquery limitations
- GPU cold start behavior
- Notebook upload requirements
- Model Registry dependencies

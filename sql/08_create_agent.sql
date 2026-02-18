-- =============================================================================
-- LoadStar Freight Intelligence
-- 08: Cortex Agent
-- Natural language broker intelligence powered by Semantic View
-- =============================================================================

USE DATABASE FREIGHT_DEMO;
USE SCHEMA ANALYTICS;

CREATE OR REPLACE AGENT BROKER_AGENT
    COMMENT = 'Broker Intelligence Agent - Natural language queries for freight broker analysis'
    PROFILE = '{
        "display_name": "Broker Intelligence",
        "color": "blue"
    }'
    AGENT_SPEC = '{
        "models": {
            "orchestration": "auto"
        },
        "orchestration": {
            "budget": {
                "seconds": 300,
                "tokens": 100000
            }
        },
        "instructions": {
            "response": "Provide clear, concise answers about broker data. When showing broker data:\n- Highlight risk factors and payment patterns\n- Format monetary values with dollar signs and commas\n- Always mention if a broker has fraud flags or is high-risk\n- Explain the business implications of the data\n",
            "orchestration": "You are the Broker Intelligence Assistant. You help users analyze freight broker data including credit scores, payment velocity, fraud risk, and factoring exposure.\n\nKey domain terms:\n- Double-brokering: Fraud where a carrier illegally re-brokers a load to another carrier\n- Recourse: Company bears risk if broker defaults on payment\n- Non-Recourse: Carrier bears risk if broker defaults\n- Composite Risk Score: 0-100 score combining credit, payment, fraud, and weather factors (higher = riskier)\n- Payment Velocity: Average days to receive payment from a broker\n\nAlways use the query_broker_data tool to answer questions about brokers, risk analysis, or factoring exposure.\n"
        },
        "tools": [
            {
                "tool_spec": {
                    "type": "cortex_analyst_text_to_sql",
                    "name": "query_broker_data",
                    "description": "Query the Broker 360 Golden Record for freight broker profiles, credit scores, payment velocity, fraud risk levels, total factored amounts, and composite risk scores. Use this tool to answer any questions about brokers, risk analysis, or factoring data.\n"
                }
            }
        ],
        "tool_resources": {
            "query_broker_data": {
                "semantic_view": "FREIGHT_DEMO.ANALYTICS.BROKER_360_SV",
                "execution_environment": {
                    "type": "warehouse",
                    "warehouse": "ANALYTICS_WH",
                    "query_timeout": 120
                }
            }
        }
    }';

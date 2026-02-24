# Demo Talk Track

## Phase 1: Data Ingestion & Workload Isolation

**Target persona: IT Ops**

> "Let me show you something. Right now, a task is inserting JSON invoices into Snowflake every 60 seconds — simulating your real-time feed. Watch the row count grow."

```sql
SELECT COUNT(*) FROM FREIGHT_DEMO.RAW.INVOICE_TRANSACTIONS_JSON;
-- Run again after 60 seconds to show growth
```

> "Notice we're on a dedicated ANALYTICS_WH warehouse. Your source Oracle DB? Completely untouched. Zero impact. That's workload isolation — no more 'Oracle sneeze' taking down analytics."

> "And here's the DS sandbox — it's a zero-copy clone. Same data, zero additional storage cost. Your data scientists experiment freely without touching production."

```sql
SELECT COUNT(*) FROM FREIGHT_DEMO.DS_SANDBOX.INVOICE_TRANSACTIONS;
```

---

## Phase 2: The Broker Object (Golden Record)

**Target persona: Product**

> "This is the heart of what we built. One row per broker. 30 columns. Auto-refreshes every 5 minutes. No ETL jobs to manage. No Domo dashboards to reconcile."

```sql
SELECT * FROM FREIGHT_DEMO.ANALYTICS.BROKER_360 LIMIT 5;
```

> "Credit score, payment velocity, fraud flags, weather risk, geospatial lane density — all in one place. This is your 'single source of truth.' No more 42 versions."

> "See the COMPOSITE_RISK_SCORE? It combines four signals: credit (0-40), payment speed (0-25), double-brokering fraud (0-30), and weather (0-10). A score of 70 means this broker is a serious risk."

---

## Phase 3: The Data Science Workbench

**Target persona: Data Science**

> "Open the notebook. Notice — no Docker, no ECS, no Kubernetes. This runs on Snowflake's Container Runtime with a GPU compute pool."

> "The model is a PyTorch neural network — two hidden layers, trained right here in the notebook. And it's registered in the Model Registry with versioning."

```sql
SHOW VERSIONS IN MODEL FREIGHT_DEMO.ML.BROKER_RISK_NET;
```

> "When your data scientists want to iterate, they clone the data, train on GPU, and register a new version. No infrastructure tickets. No DevOps."

---

## Phase 4: Production Inference

**Target persona: Product**

> "The scoring UDF is the single source of truth for your recommendation engine. Give it a driver and a load, it returns a match score from 0 to 1."

```sql
SELECT FREIGHT_DEMO.ML.GET_RECOMMENDATION_SCORE(1, 1);
```

> "Sub-500ms. Your mobile app calls this in real-time. No batch processing. And the recommendations table has 2000 pre-computed scores for instant lookup."

```sql
SELECT RISK_LEVEL, COUNT(*) AS CNT, ROUND(AVG(RECOMMENDATION_SCORE), 4) AS AVG_SCORE
FROM FREIGHT_DEMO.ML.CARRIERMATCH_RECOMMENDATIONS
GROUP BY RISK_LEVEL ORDER BY AVG_SCORE DESC;
```

---

## Phase 5: Chat with Data

**Target persona: Product**

> "Now the part Michael will love. Ask the agent a question in plain English."

Test questions:
1. "Who are our top 5 brokers by total factored amount?"
2. "Which brokers have CRITICAL fraud risk?"
3. "What's the average days to pay by factoring type?"

> "No SQL. No JIRA ticket. No waiting for a data analyst. Your product team can self-serve."

---

## Phase 6: Command Map & Route Planning

**Target persona: Operations / Product**

> "Open the LoadStar Commander app. This is the Command Map — a visual dispatch console for driver-load matching."

> "Notice the routes aren't straight lines. They follow actual roads. That's OpenRouteService Native App running inside Snowflake on Container Services."

Demo the ORS toggle:

> "Watch this — I'll toggle on the live demo route."

*Enable the "Live ORS demo route" toggle*

> "That orange route you see? It just called the ORS DIRECTIONS function in real-time. Dallas to Amarillo, 590 kilometers, following I-40 and US-287. The driving-hgv profile optimizes for truck routing — considers bridge heights, weight limits, truck stops."

> "The cross-country routes are pre-computed because they go outside Texas, but the architecture is the same. ORS generates the polylines, we store them, and pydeck renders them as smooth curves on the map."

Show the ORS attribution badge:

> "See the badge in the control panel? OpenRouteService Native App, Snowpark Container Services, driving-hgv profile. This is enterprise routing running entirely inside your Snowflake account. No external API calls. No egress charges. Full data sovereignty."

---

## Closing

> "Let's recap: One platform. Streaming ingestion without touching Oracle. A golden record that auto-refreshes. GPU-trained ML models without Docker. Natural language queries without SQL. PII masked by policy, not by trust. All deployed from a single git repo in under 30 minutes."

> "Questions?"

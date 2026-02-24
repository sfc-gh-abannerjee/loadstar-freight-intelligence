"""
LoadStar Commander — Freight intelligence dashboard.
Runs on Snowflake Container Runtime (SPCS).
"""

import json
import os
import re as _re

import pandas as pd
import pydeck as pdk
import plotly.graph_objects as go
import requests
import sseclient

import streamlit as st

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="LoadStar Commander",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Neumorphism CSS on Stellar dark-mode palette
# ---------------------------------------------------------------------------
NEUMORPH_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --canvas: #191e24;
    --surface: #1e252f;
    --border: #293246;
    --text-primary: #bdc4d5;
    --text-secondary: #9fabc1;
    --text-header: #bdc4d5;
    --accent: #1a6ce7;
    --accent-light: #5999f8;
    --success: #1db588;
    --warning: #e8a317;
    --danger: #d3132f;
    --danger-light: #ef405e;
    --shadow-dark: #12161c;
    --shadow-light: #242d38;
}

html, body, [class*="st-"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Neumorphic card */
.neu-card {
    background: var(--surface);
    border-radius: 16px;
    padding: 24px;
    box-shadow: 8px 8px 16px var(--shadow-dark),
                -8px -8px 16px var(--shadow-light);
    margin-bottom: 16px;
}

.neu-card-inset {
    background: var(--surface);
    border-radius: 12px;
    padding: 20px;
    box-shadow: inset 4px 4px 8px var(--shadow-dark),
                inset -4px -4px 8px var(--shadow-light);
    margin-bottom: 12px;
}

/* Stat card */
.stat-card {
    background: var(--surface);
    border-radius: 16px;
    padding: 20px 24px;
    box-shadow: 6px 6px 12px var(--shadow-dark),
                -6px -6px 12px var(--shadow-light);
    text-align: center;
    min-height: 100px;
}
.stat-card .stat-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--text-header);
    margin: 4px 0;
}
.stat-card .stat-label {
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Risk badge */
.risk-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
}
.risk-low { background: rgba(29,181,136,0.15); color: #1db588; }
.risk-medium { background: rgba(232,163,23,0.15); color: #e8a317; }
.risk-high { background: rgba(211,19,47,0.15); color: #ef405e; }
.risk-critical { background: rgba(211,19,47,0.25); color: #ef405e; font-weight: 700; }
.risk-na { background: rgba(159,171,193,0.15); color: #9fabc1; }

/* Match score gauge */
.match-gauge {
    width: 64px; height: 64px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.9rem; font-weight: 700;
    box-shadow: inset 3px 3px 6px var(--shadow-dark),
                inset -3px -3px 6px var(--shadow-light);
}

/* Section header */
.section-header {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-header);
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--accent);
    display: inline-block;
}

/* App title */
.app-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text-header);
    margin: 0;
}
.app-subtitle {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-top: 2px;
}

/* Fix for Material Icons not loading in SiS - hide broken icon text in expander */
[data-testid="stExpander"] summary > span:first-child {
    display: none !important;
}
[data-testid="stExpander"] summary::before {
    content: "▶";
    margin-right: 8px;
    font-size: 0.8rem;
    display: inline-block;
    transition: transform 0.3s ease;
}
[data-testid="stExpander"] details[open] summary::before {
    transform: rotate(90deg);
}

/* Collapsible SQL code blocks (native <details> inside st.html) */
.sql-details {
    border-left: 3px solid #9c5bea;
    padding-left: 12px;
    margin-bottom: 12px;
    max-width: 100%;
    overflow: hidden;
}
.sql-details summary {
    font-size: 0.75rem;
    color: #9c5bea;
    font-weight: 600;
    cursor: pointer;
    user-select: none;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 6px;
}
.sql-details summary::-webkit-details-marker { display: none; }
.sql-details summary::before {
    content: "▶";
    font-size: 0.6rem;
    display: inline-block;
    transition: transform 0.3s ease;
}
.sql-details[open] summary::before {
    transform: rotate(90deg);
}
.sql-details pre {
    background: #13161c;
    border-radius: 6px;
    padding: 12px 14px;
    margin: 8px 0 0 0;
    overflow-x: auto;
    max-height: 320px;
    overflow-y: auto;
    font-size: 0.78rem;
    line-height: 1.5;
    border: 1px solid rgba(156,91,234,0.15);
    box-shadow: inset 0 1px 4px rgba(0,0,0,0.3);
    white-space: pre-wrap;
    word-break: break-word;
    max-width: 100%;
    box-sizing: border-box;
}
.sql-details pre::-webkit-scrollbar { width: 6px; height: 6px; }
.sql-details pre::-webkit-scrollbar-track { background: transparent; }
.sql-details pre::-webkit-scrollbar-thumb { background: #3a3f4b; border-radius: 3px; }
.sql-details code {
    color: #e0e6ed;
    font-family: 'SF Mono', Monaco, Consolas, 'Courier New', monospace;
    white-space: pre-wrap;
    word-break: break-word;
}

/* Agent thinking step cards */
.thinking-section {
    background: var(--surface);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 10px;
    border-left: 3px solid var(--accent);
}
.thinking-section.planning { border-left-color: #1a6ce7; }
.thinking-section.tools { border-left-color: #e8a317; }
.thinking-section.reasoning { border-left-color: #1db588; }
.section-label {
    font-weight: 600;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
    color: var(--text-secondary);
}
.step-item {
    font-size: 0.85rem;
    color: var(--text-primary);
    padding: 3px 0;
    display: flex;
    align-items: flex-start;
    gap: 8px;
}
.step-item .icon { flex-shrink: 0; }
.reasoning-text {
    font-size: 0.8rem;
    color: var(--text-secondary);
    line-height: 1.5;
    white-space: pre-wrap;
}
</style>
"""
st.html(NEUMORPH_CSS)


# ---------------------------------------------------------------------------
# Snowflake connection (thread-safe for container runtime)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_session():
    return st.connection("snowflake").session()


@st.cache_data(ttl=300)
def run_query(sql: str) -> pd.DataFrame:
    session = get_session()
    return session.sql(sql).to_pandas()


# ---------------------------------------------------------------------------
# Cortex Agent helper (container runtime auth)
# ---------------------------------------------------------------------------
def call_cortex_agent_streaming(question: str, broker_context: str = ""):
    """Call the Broker Intelligence Agent via REST API with streaming.
    
    Yields tuples of (mode, text) where mode is one of:
    - "thinking": Agent's reasoning tokens (shown during planning)
    - "status": Status updates like "Planning..." or "Executing tool..."
    - "answer": Final answer tokens
    """
    host = os.getenv("SNOWFLAKE_HOST")
    if not host:
        yield ("answer", "Agent unavailable — SNOWFLAKE_HOST not set.")
        return
    try:
        token = open("/snowflake/session/token", "r").read()
    except FileNotFoundError:
        yield ("answer", "Agent unavailable — session token not found.")
        return

    # Add broker context to the question if provided
    full_question = f"Regarding broker '{broker_context}': {question}" if broker_context else question

    url = (
        f"https://{host}/api/v2/databases/APEX_CAPITAL_DEMO"
        f"/schemas/ANALYTICS/agents/APEX_BROKER_AGENT:run"
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Snowflake-Authorization-Token-Type": "OAUTH",
        "Accept": "text/event-stream",
    }
    payload = {
        "stream": True,
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": full_question}]
        }],
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120, stream=True)
        if resp.status_code != 200:
            yield ("answer", f"Agent returned HTTP {resp.status_code}")
            return
        
        # Use sseclient to properly parse SSE events
        client = sseclient.SSEClient(resp)
        thinking_text = ""
        answer_text = ""
        last_status = ""
        
        for event in client.events():
            try:
                # Skip empty data
                if not event.data or event.data.strip() == "" or event.data == "[DONE]":
                    continue
                
                parsed = json.loads(event.data)
                event_type = event.event or ""
                
                # Helper: check if text looks like actual SQL
                _SQL_STARTS = ("SELECT", "WITH", "INSERT", "UPDATE", "DELETE",
                               "CREATE", "ALTER", "DROP", "MERGE", "CALL",
                               "SHOW", "DESCRIBE", "EXPLAIN", "GRANT", "REVOKE")

                def _is_sql(text):
                    if not text or not isinstance(text, str):
                        return False
                    stripped = text.strip().upper()
                    return any(stripped.startswith(kw) for kw in _SQL_STARTS)

                # Helper to find SQL in nested structures
                def find_sql_in_data(data, depth=0):
                    if depth > 5:  # Prevent infinite recursion
                        return None
                    if isinstance(data, str):
                        stripped = data.strip()
                        if _is_sql(stripped):
                            return stripped
                    elif isinstance(data, dict):
                        # Check common SQL field names first
                        for key in ("sql", "generated_sql", "sql_query"):
                            if key in data and data[key] and _is_sql(data[key]):
                                return data[key]
                        # "query" and "statement" often hold NL text — only
                        # return them if they actually look like SQL
                        for key in ("query", "statement"):
                            if key in data and data[key] and _is_sql(data[key]):
                                return data[key]
                        # Recursively search values
                        for v in data.values():
                            result = find_sql_in_data(v, depth + 1)
                            if result:
                                return result
                    elif isinstance(data, list):
                        for item in data:
                            result = find_sql_in_data(item, depth + 1)
                            if result:
                                return result
                    return None

                # Helper to find NL description text from query/statement fields
                def find_description_in_data(data, depth=0):
                    """Extract natural-language description from query/statement
                    fields that are NOT actual SQL."""
                    if depth > 5:
                        return None
                    if isinstance(data, dict):
                        for key in ("query", "statement"):
                            val = data.get(key)
                            if val and isinstance(val, str) and not _is_sql(val):
                                return val.strip()
                        for v in data.values():
                            result = find_description_in_data(v, depth + 1)
                            if result:
                                return result
                    elif isinstance(data, list):
                        for item in data:
                            result = find_description_in_data(item, depth + 1)
                            if result:
                                return result
                    return None
                
                # Status events (Planning, Executing tool, etc.)
                if event_type == "response.status":
                    status = parsed.get("status", "")
                    message = parsed.get("message", "")
                    if message and message != last_status:
                        last_status = message
                        yield ("status", message)
                    # Check if this status event contains SQL data
                    desc = find_description_in_data(parsed)
                    if desc and desc != last_status:
                        last_status = desc
                        yield ("status", desc)
                    sql = find_sql_in_data(parsed)
                    if sql:
                        yield ("sql", sql)
                
                # Thinking delta events (reasoning tokens)
                elif event_type == "response.thinking.delta":
                    text = parsed.get("text", "")
                    if text:
                        thinking_text += text
                        yield ("thinking", thinking_text)
                
                # Tool result status (shows what tool is running)
                elif event_type == "response.tool_result.status":
                    message = parsed.get("message", "")
                    if message and message != last_status:
                        last_status = message
                        yield ("status", message)
                    # Check for NL description then SQL in status data
                    desc = find_description_in_data(parsed)
                    if desc and desc != last_status:
                        last_status = desc
                        yield ("status", desc)
                    sql = find_sql_in_data(parsed)
                    if sql:
                        yield ("sql", sql)
                
                # Analyst tool result delta (new API schema — SQL at delta.sql)
                elif event_type == "response.tool_result.analyst.delta":
                    desc = find_description_in_data(parsed)
                    if desc and desc != last_status:
                        last_status = desc
                        yield ("status", desc)
                    sql = find_sql_in_data(parsed)
                    if sql:
                        yield ("sql", sql)
                
                # Tool use/call events (contains the SQL being sent to tool)
                elif event_type in ("response.tool_use", "response.tool_call", "tool_use"):
                    desc = find_description_in_data(parsed)
                    if desc and desc != last_status:
                        last_status = desc
                        yield ("status", desc)
                    sql = find_sql_in_data(parsed)
                    if sql:
                        yield ("sql", sql)
                
                # Tool result (contains SQL queries and other tool outputs)
                elif event_type == "response.tool_result":
                    desc = find_description_in_data(parsed)
                    if desc and desc != last_status:
                        last_status = desc
                        yield ("status", desc)
                    sql = find_sql_in_data(parsed)
                    if sql:
                        yield ("sql", sql)
                
                # Text delta events (answer tokens)
                elif event_type == "response.text.delta":
                    text = parsed.get("text", "")
                    if text:
                        answer_text += text
                        yield ("answer", answer_text)
                
                # Message delta events
                elif event_type == "message.delta":
                    delta = parsed.get("delta", {})
                    if isinstance(delta, dict):
                        content = delta.get("content", [])
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text = item.get("text", "")
                                    if text:
                                        answer_text += text
                                        yield ("answer", answer_text)
                        elif isinstance(content, dict):
                            if content.get("type") == "text":
                                text = content.get("text", "")
                                if text:
                                    answer_text += text
                                    yield ("answer", answer_text)
                
                # Final response event (contains full message)
                elif event_type == "response":
                    # Extract final text from response if we haven't collected anything
                    if not answer_text:
                        content = parsed.get("content", [])
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "text":
                                    text = item.get("text", "")
                                    if text:
                                        answer_text = text
                                        yield ("answer", answer_text)
                
                # Fallback: try to extract text from delta.content structure
                elif "delta" in parsed:
                    delta = parsed["delta"]
                    if isinstance(delta, dict):
                        content = delta.get("content", {})
                        if isinstance(content, dict) and content.get("type") == "text":
                            text = content.get("text", "")
                            if text:
                                answer_text += text
                                yield ("answer", answer_text)
                        elif isinstance(content, str):
                            answer_text += content
                            yield ("answer", answer_text)
                    elif isinstance(delta, str):
                        answer_text += delta
                        yield ("answer", answer_text)
                
                # Catch-all: check any unhandled event for SQL
                else:
                    sql = find_sql_in_data(parsed)
                    if sql:
                        yield ("sql", sql)
                
            except json.JSONDecodeError:
                continue
            except Exception:
                continue
        
        if not answer_text:
            yield ("answer", "No response from agent.")
    except requests.exceptions.Timeout:
        yield ("answer", "Agent request timed out. Please try again.")
    except Exception as e:
        yield ("answer", f"Agent error: {str(e)}")


def categorize_status(message: str) -> str:
    """Categorize a status message into planning, tool, or other."""
    lower = message.lower()
    planning_keywords = ["planning", "choosing", "rethinking", "reviewing", "next steps", "data sources"]
    tool_keywords = ["running", "streaming", "getting", "executing", "context", "sql"]
    
    if any(kw in lower for kw in planning_keywords):
        return "planning"
    elif any(kw in lower for kw in tool_keywords):
        return "tool"
    return "planning"  # Default to planning for unknown status


def _highlight_sql(sql_text: str) -> str:
    """Apply SQL syntax highlighting via inline styles (two-pass to avoid cross-matching)."""
    import html as html_mod
    escaped = html_mod.escape(sql_text)

    # --- Pass 1: protect strings and comments with placeholders ---
    _hl_slots: list[str] = []

    def _slot(html_frag: str) -> str:
        idx = len(_hl_slots)
        _hl_slots.append(html_frag)
        return f"\x00HL{idx}\x00"

    # Block comments  /* ... */
    escaped = _re.sub(
        r'/\*.*?\*/',
        lambda m: _slot(f'<span style="color:#5c6370;font-style:italic">{m.group()}</span>'),
        escaped, flags=_re.DOTALL,
    )
    # Line comments  -- ...
    escaped = _re.sub(
        r'(--.*?)$',
        lambda m: _slot(f'<span style="color:#5c6370;font-style:italic">{m.group()}</span>'),
        escaped, flags=_re.MULTILINE,
    )
    # Single-quoted strings (HTML-escaped apostrophes)
    escaped = _re.sub(
        r"(&#x27;[^&]*?&#x27;)",
        lambda m: _slot(f'<span style="color:#98c379">{m.group()}</span>'),
        escaped,
    )

    # --- Pass 2: highlight keywords, functions, numbers ---
    kw = (r'\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|CROSS|FULL|ON|AND|OR|NOT|IN|IS|NULL|'
          r'AS|ORDER|BY|GROUP|HAVING|LIMIT|OFFSET|UNION|ALL|DISTINCT|INSERT|INTO|VALUES|UPDATE|SET|'
          r'DELETE|CREATE|ALTER|DROP|TABLE|VIEW|INDEX|WITH|CASE|WHEN|THEN|ELSE|END|BETWEEN|LIKE|'
          r'EXISTS|ASC|DESC|TOP|OVER|PARTITION|WINDOW|ROWS|RANGE|PRECEDING|FOLLOWING|CURRENT|ROW|'
          r'RECURSIVE|LATERAL|QUALIFY|ILIKE|PIVOT|UNPIVOT|EXCLUDE|REPLACE|RENAME)\b')
    escaped = _re.sub(kw, r'<span style="color:#c678dd;font-weight:bold">\1</span>', escaped, flags=_re.IGNORECASE)

    # Built-in functions
    fn = (r'\b(COUNT|SUM|AVG|MIN|MAX|COALESCE|NVL|IFF|IFNULL|NULLIF|CAST|TRY_CAST|'
          r'TO_DATE|TO_TIMESTAMP|TO_NUMBER|TO_VARCHAR|DATEADD|DATEDIFF|DATE_TRUNC|'
          r'ROUND|FLOOR|CEIL|ABS|UPPER|LOWER|TRIM|LENGTH|SUBSTR|SUBSTRING|CONCAT|'
          r'SPLIT_PART|REGEXP_SUBSTR|REGEXP_REPLACE|REGEXP_LIKE|LISTAGG|ARRAY_AGG|'
          r'ROW_NUMBER|RANK|DENSE_RANK|LAG|LEAD|FIRST_VALUE|LAST_VALUE|NTH_VALUE|'
          r'PARSE_JSON|OBJECT_CONSTRUCT|FLATTEN|GET|GET_PATH)\s*(?=\()')
    escaped = _re.sub(fn, r'<span style="color:#61afef">\1</span>', escaped, flags=_re.IGNORECASE)

    # Other function-like identifiers  (WORD followed by open-paren)
    escaped = _re.sub(r'\b([A-Z_]\w*)\s*(?=\()', r'<span style="color:#61afef">\1</span>', escaped)

    # Numeric literals
    escaped = _re.sub(r'\b(\d+(?:\.\d+)?)\b', r'<span style="color:#d19a66">\1</span>', escaped)

    # --- Restore protected slots ---
    for i, frag in enumerate(_hl_slots):
        escaped = escaped.replace(f"\x00HL{i}\x00", frag)

    return escaped


def render_thinking_html(steps: list) -> str:
    """Render thinking steps as a bare HTML fragment with inline styles for ``st.html()``."""
    import html as html_mod

    parts = []
    for step in steps:
        category = step.get("category", "planning")
        text = step.get("text", "")
        step_reasoning = step.get("reasoning", "")

        reasoning_block = ""
        if step_reasoning:
            display = step_reasoning
            if len(display) > 1500:
                display = display[:1500] + "\u2026"
            reasoning_block = (
                '<div style="font-size:0.75rem;color:#9fabc1;line-height:1.4;white-space:pre-wrap;'
                'margin:4px 0 0 24px;padding:6px 10px;background:rgba(30,37,47,0.6);'
                'border-radius:4px;border-left:2px solid #1db588;max-height:200px;overflow-y:auto">'
                f'{html_mod.escape(display)}</div>'
            )

        if category == "sql":
            highlighted = _highlight_sql(text)
            parts.append(
                '<details open class="sql-details">'
                '<summary>\U0001f4ca SQL Query'
                '<span style="margin-left:auto;font-size:0.6rem;background:#9c5bea22;'
                'color:#9c5bea;padding:1px 6px;border-radius:3px;font-weight:400">SQL</span>'
                '</summary>'
                f'<pre><code>{highlighted}</code></pre></details>'
            )
        else:
            icon = "\u2713" if category == "planning" else "\u26a1"
            color = "#1a6ce7" if category == "planning" else "#e8a317"
            parts.append(
                f'<div style="font-size:0.85rem;color:#bdc4d5;border-left:3px solid {color};'
                f'padding-left:12px;margin-bottom:8px">'
                f'<span style="margin-right:6px">{icon}</span> {html_mod.escape(text)}'
                f'{reasoning_block}</div>'
            )

    if not parts:
        body = '<div style="padding:12px 0"><em style="color:#bdc4d5">\u23f3 Processing...</em></div>'
    else:
        body = "".join(parts)

    return (
        '<div style="padding:8px 4px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;'
        f'max-width:100%;overflow:hidden;box-sizing:border-box">{body}</div>'
    )


def call_cortex_agent(question: str, broker_context: str = "") -> str:
    """Call the Broker Intelligence Agent via REST API (non-streaming fallback)."""
    host = os.getenv("SNOWFLAKE_HOST")
    if not host:
        return "Agent unavailable — SNOWFLAKE_HOST not set."
    try:
        token = open("/snowflake/session/token", "r").read()
    except FileNotFoundError:
        return "Agent unavailable — session token not found."

    full_question = f"Regarding broker '{broker_context}': {question}" if broker_context else question

    url = (
        f"https://{host}/api/v2/databases/APEX_CAPITAL_DEMO"
        f"/schemas/ANALYTICS/agents/APEX_BROKER_AGENT:run"
    )
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Snowflake-Authorization-Token-Type": "OAUTH",
        "Accept": "application/json",
    }
    payload = {
        "stream": False,
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": full_question}]
        }],
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        if resp.status_code != 200:
            return f"Agent returned HTTP {resp.status_code}"
        data = resp.json()
        
        # Extract text from the response - handle multiple formats
        text_parts = []
        
        # Check for 'message' (singular) or 'messages' (plural)
        messages = data.get("messages", [])
        if not messages and "message" in data:
            messages = [data["message"]]
        
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", [])
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
        
        if text_parts:
            return "\n".join(filter(None, text_parts))
        
        # Fallback: try to find any text in the response
        if "text" in data:
            return data["text"]
        
        return "No response from agent."
    except requests.exceptions.Timeout:
        return "Agent request timed out. Please try again."
    except Exception as e:
        return f"Agent error: {str(e)}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def risk_badge(level: str) -> str:
    level_str = str(level).upper() if level else "N/A"
    css_class = {
        "LOW": "risk-low",
        "MEDIUM": "risk-medium",
        "HIGH": "risk-high",
        "CRITICAL": "risk-critical",
        "N/A": "risk-na",
        "NONE": "risk-na",
    }.get(level_str, "risk-na")
    return f'<span class="risk-badge {css_class}">{level}</span>'


def stat_card(label: str, value: str, color: str = "var(--text-header)") -> str:
    return f"""
    <div class="stat-card">
        <div class="stat-label">{label}</div>
        <div class="stat-value" style="color:{color}">{value}</div>
    </div>
    """


def match_color(score: float) -> str:
    if score >= 0.8:
        return "#1db588"
    if score >= 0.6:
        return "#5999f8"
    if score >= 0.4:
        return "#e8a317"
    return "#ef405e"


# ---------------------------------------------------------------------------
# Title bar
# ---------------------------------------------------------------------------
st.html(
    '<div style="padding:8px 0 16px 0;">'
    '<p class="app-title">LoadStar Commander</p>'
    '<p class="app-subtitle">Freight intelligence platform</p>'
    "</div>"
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_map, tab_match, tab_broker = st.tabs(
    [
        ":material/map: Command map",
        ":material/handshake: Match engine",
        ":material/person_search: Broker 360",
    ]
)

# ===== TAB 1: Command Map ===================================================
with tab_map:

    @st.cache_data(ttl=300)
    def load_map_data():
        recs = run_query("""
            SELECT r.DRIVER_ID, r.LOAD_ID, r.RECOMMENDATION_SCORE, r.RISK_LEVEL,
                   r.ORIGIN_CITY, r.ORIGIN_STATE,
                   r.DESTINATION_CITY, r.DESTINATION_STATE,
                   r.TOTAL_RATE, r.EQUIPMENT_REQUIRED, r.MILES,
                   r.ORIGIN_LATITUDE, r.ORIGIN_LONGITUDE,
                   r.BROKER_NAME, r.CREDIT_SCORE, r.FRAUD_RISK_LEVEL,
                   r.COMPOSITE_RISK_SCORE,
                   c.CARRIER_NAME, c.HOME_LATITUDE, c.HOME_LONGITUDE,
                   g.LATITUDE AS DEST_LAT, g.LONGITUDE AS DEST_LON
            FROM APEX_CAPITAL_DEMO.ANALYTICS.LOADSTAR_RECOMMENDATIONS_V r
            JOIN APEX_CAPITAL_DEMO.RAW.CARRIER_PROFILES c
                ON c.CARRIER_ID = r.DRIVER_ID
            LEFT JOIN APEX_CAPITAL_DEMO.RAW.CITY_GEOCODES g
                ON SPLIT_PART(r.DESTINATION_CITY, ',', 1) = g.CITY_NAME
            ORDER BY r.RECOMMENDATION_SCORE DESC
        """)
        weather = run_query("""
            SELECT CITY_NAME,
                   ROUND(AVG(AVG_TEMP_F), 1) AS AVG_TEMP_F,
                   ROUND(MAX(MAX_WIND_MPH), 1) AS MAX_WIND_MPH,
                   ROUND(SUM(PRECIPITATION_IN), 2) AS PRECIPITATION_IN,
                   WEATHER_RISK_LEVEL
            FROM APEX_CAPITAL_DEMO.RAW.TEXAS_WEATHER
            GROUP BY CITY_NAME, WEATHER_RISK_LEVEL
        """)
        return recs, weather

    @st.cache_data(ttl=300)
    def load_route_polylines():
        """Load pre-computed road-following route polylines from ORS."""
        return run_query("""
            SELECT ORIGIN_CITY, DEST_CITY, COORDINATES, DISTANCE_KM
            FROM APEX_CAPITAL_DEMO.RAW.ROUTE_POLYLINES
        """)

    @st.cache_data(ttl=60)
    def get_ors_live_route(origin_lon: float, origin_lat: float, dest_lon: float, dest_lat: float):
        """Call ORS Native App DIRECTIONS function for live truck routing."""
        result = run_query(f"""
            SELECT OPENROUTESERVICE_NATIVE_APP.CORE.DIRECTIONS(
                'driving-hgv',
                [{origin_lon}, {origin_lat}],
                [{dest_lon}, {dest_lat}]
            ) AS route_json
        """)
        if result.empty:
            return None
        route_data = result.iloc[0]["ROUTE_JSON"]
        if isinstance(route_data, str):
            route_data = json.loads(route_data)
        # Check for error response
        if "error" in route_data:
            return None
        # Extract coordinates from GeoJSON
        try:
            coords = route_data["features"][0]["geometry"]["coordinates"]
            distance_m = route_data["features"][0]["properties"]["segments"][0]["distance"]
            return {"coordinates": coords, "distance_km": round(distance_m / 1000, 1)}
        except (KeyError, IndexError):
            return None

    recs_map_df, weather_df = load_map_data()
    route_polylines_df = load_route_polylines()

    # Risk-level color mapping
    _RISK_COLORS = {
        "STRONG_MATCH": "#1db588",  # green
        "GOOD_MATCH": "#1a6ce7",    # blue
        "MEDIUM_MATCH": "#e8a317",  # orange
        "NO_MATCH": "#e05252",      # red
    }
    _RISK_LABELS = {
        "STRONG_MATCH": "Strong match",
        "GOOD_MATCH": "Good match",
        "MEDIUM_MATCH": "Medium match",
        "NO_MATCH": "No match",
    }

    # --- Sidebar filters (right column) ---
    map_col, ctrl_col = st.columns([3, 1])

    with ctrl_col:
        st.html('<div class="section-header">Filters</div>')

        # Driver selector
        driver_opts = (
            recs_map_df[["DRIVER_ID", "CARRIER_NAME"]]
            .drop_duplicates()
            .sort_values("DRIVER_ID")
        )
        driver_labels = driver_opts.apply(
            lambda r: f"Driver {r['DRIVER_ID']} — {r['CARRIER_NAME']}", axis=1
        ).tolist()
        sel_driver_label = st.selectbox("Driver", driver_labels, label_visibility="collapsed")
        sel_driver_id = int(sel_driver_label.split(" — ")[0].replace("Driver ", ""))

        # Equipment multiselect
        all_equip = sorted(recs_map_df["EQUIPMENT_REQUIRED"].dropna().unique().tolist())
        sel_equip = st.multiselect("Equipment type", all_equip, default=all_equip)

        # Risk level multiselect
        all_risks = ["STRONG_MATCH", "GOOD_MATCH", "MEDIUM_MATCH", "NO_MATCH"]
        sel_risks = st.multiselect(
            "Match quality",
            all_risks,
            default=["STRONG_MATCH", "GOOD_MATCH"],
            format_func=lambda x: _RISK_LABELS.get(x, x),
        )

        # Minimum rate slider
        rate_min = int(recs_map_df["TOTAL_RATE"].min()) if len(recs_map_df) else 0
        rate_max = int(recs_map_df["TOTAL_RATE"].max()) if len(recs_map_df) else 10000
        min_rate = st.slider("Minimum rate ($)", rate_min, rate_max, rate_min, step=100)

        # --- ORS Integration Demo ---
        st.html('<div class="section-header" style="margin-top:24px;">OpenRouteService</div>')
        show_ors_demo = st.toggle("Live ORS demo route", value=False, 
                                   help="Show a live route computed by ORS Native App (Dallas → Amarillo)")
        
        st.html('''
            <div style="margin-top:12px; padding:10px; background:rgba(89,153,248,0.1); 
                        border-radius:8px; border-left:3px solid #5999f8;">
                <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">
                    ROUTING ENGINE
                </div>
                <div style="font-size:13px; font-weight:500; color:var(--text-header);">
                    OpenRouteService Native App
                </div>
                <div style="font-size:11px; color:var(--text-muted); margin-top:4px;">
                    Snowpark Container Services • driving-hgv profile
                </div>
            </div>
        ''')

    # --- Apply filters ---
    filtered_df = recs_map_df[
        (recs_map_df["DRIVER_ID"] == sel_driver_id)
        & (recs_map_df["EQUIPMENT_REQUIRED"].isin(sel_equip))
        & (recs_map_df["RISK_LEVEL"].isin(sel_risks))
        & (recs_map_df["TOTAL_RATE"] >= min_rate)
    ].copy()

    # --- KPI row (dynamic, filtered) ---
    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        st.html(stat_card("Matched loads", str(len(filtered_df))))
    with kpi_cols[1]:
        avg_rate = f"${filtered_df['TOTAL_RATE'].mean():,.0f}" if len(filtered_df) else "$0"
        st.html(stat_card("Avg rate", avg_rate, "var(--success)"))
    with kpi_cols[2]:
        strong_ct = len(filtered_df[filtered_df["RISK_LEVEL"] == "STRONG_MATCH"])
        st.html(stat_card("Strong matches", str(strong_ct), "var(--success)"))
    with kpi_cols[3]:
        low_fraud = len(filtered_df[filtered_df["FRAUD_RISK_LEVEL"] == "LOW"])
        st.html(stat_card("Low fraud risk", str(low_fraud)))

    # --- Pydeck color helpers ---
    _RISK_RGBA = {
        "STRONG_MATCH": [29, 181, 136, 200],   # green
        "GOOD_MATCH": [26, 108, 231, 200],      # blue
        "MEDIUM_MATCH": [232, 163, 23, 200],     # orange
        "NO_MATCH": [224, 82, 82, 200],          # red
    }

    # --- Build pydeck map ---
    event = None
    with map_col:
        if filtered_df.empty:
            st.warning("No loads match your filters. Try adjusting the criteria.")
        else:
            home_lat = filtered_df.iloc[0]["HOME_LATITUDE"]
            home_lon = filtered_df.iloc[0]["HOME_LONGITUDE"]
            carrier_name = filtered_df.iloc[0]["CARRIER_NAME"]

            # Prepare origin markers dataframe
            markers_df = filtered_df.copy()
            markers_df["color"] = markers_df["RISK_LEVEL"].map(
                lambda x: _RISK_RGBA.get(x, [128, 128, 128, 180])
            )
            markers_df["risk_label"] = markers_df["RISK_LEVEL"].map(
                lambda x: _RISK_LABELS.get(x, x)
            )
            markers_df["score_pct"] = (markers_df["RECOMMENDATION_SCORE"] * 100).round(0).astype(int).astype(str) + "%"
            markers_df["rate_fmt"] = markers_df["TOTAL_RATE"].apply(lambda x: f"${x:,.0f}")

            # Home base marker — populate all tooltip-referenced columns
            # so the global tooltip renders meaningful info for this layer
            home_df = pd.DataFrame([{
                "lat": home_lat, "lon": home_lon,
                "color": [156, 91, 234, 220],
                "name": f"{carrier_name} — Home base",
                "LOAD_ID": f"🏠 Driver Home Base",
                "ORIGIN_CITY": carrier_name,
                "DESTINATION_CITY": f"({sel_driver_id})",
                "rate_fmt": "—",
                "MILES": "—",
                "EQUIPMENT_REQUIRED": "—",
                "BROKER_NAME": "—",
                "CREDIT_SCORE": "—",
                "FRAUD_RISK_LEVEL": "—",
                "risk_label": "Home",
                "score_pct": "—",
            }])

            # Road-following route paths (origin -> destination)
            # Join filtered loads with pre-computed route polylines
            route_records = []
            for _, row in markers_df.iterrows():
                origin = row.get("ORIGIN_CITY")
                dest = row.get("DESTINATION_CITY")
                if origin and dest:
                    # Find matching polyline from pre-computed routes
                    match = route_polylines_df[
                        (route_polylines_df["ORIGIN_CITY"] == origin) &
                        (route_polylines_df["DEST_CITY"] == dest)
                    ]
                    if not match.empty:
                        coords = match.iloc[0]["COORDINATES"]
                        # Convert from Snowflake ARRAY to Python list if needed
                        if isinstance(coords, str):
                            coords = json.loads(coords)
                        route_records.append({
                            "path": coords,  # [[lon, lat], ...] format for PathLayer
                            "color": _RISK_RGBA.get(row["RISK_LEVEL"], [128, 128, 128, 160]),
                            "origin": origin,
                            "destination": dest,
                        })
            routes_df = pd.DataFrame(route_records) if route_records else pd.DataFrame()

            layers = []

            # Road-following route paths layer (PathLayer)
            if not routes_df.empty:
                layers.append(
                    pdk.Layer(
                        "PathLayer",
                        data=routes_df,
                        id="route-paths",
                        get_path="path",
                        get_color="color",
                        get_width=3,
                        width_min_pixels=2,
                        width_max_pixels=6,
                        pickable=False,
                        opacity=0.5,
                    )
                )

            # Live ORS demo route (Dallas → Amarillo) when toggle enabled
            if show_ors_demo:
                # Call ORS Native App in real-time
                ors_route = get_ors_live_route(-96.764, 32.751, -101.837, 35.231)
                if ors_route:
                    ors_demo_df = pd.DataFrame([{
                        "path": ors_route["coordinates"],
                        "color": [255, 140, 0, 220],  # Bright orange for demo
                    }])
                    layers.append(
                        pdk.Layer(
                            "PathLayer",
                            data=ors_demo_df,
                            id="ors-live-demo",
                            get_path="path",
                            get_color="color",
                            get_width=5,
                            width_min_pixels=3,
                            width_max_pixels=8,
                            pickable=False,
                            opacity=0.9,
                        )
                    )
                    # Add markers for ORS demo route endpoints
                    ors_markers = pd.DataFrame([
                        {"lon": -96.764, "lat": 32.751, "name": "Dallas (ORS Live)", "color": [255, 140, 0, 255]},
                        {"lon": -101.837, "lat": 35.231, "name": "Amarillo (ORS Live)", "color": [255, 140, 0, 255]},
                    ])
                    layers.append(
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=ors_markers,
                            id="ors-demo-markers",
                            get_position=["lon", "lat"],
                            get_fill_color="color",
                            get_radius=22000,
                            radius_min_pixels=6,
                            radius_max_pixels=16,
                            pickable=False,
                        )
                    )

            # Origin load markers
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=markers_df,
                    id="load-origins",
                    get_position=["ORIGIN_LONGITUDE", "ORIGIN_LATITUDE"],
                    get_fill_color="color",
                    get_radius=18000,
                    radius_min_pixels=5,
                    radius_max_pixels=14,
                    pickable=True,
                    auto_highlight=True,
                    highlight_color=[255, 255, 255, 80],
                )
            )

            # Driver home icon (larger, purple)
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=home_df,
                    id="driver-home",
                    get_position=["lon", "lat"],
                    get_fill_color="color",
                    get_radius=24000,
                    radius_min_pixels=8,
                    radius_max_pixels=18,
                    pickable=True,
                    auto_highlight=True,
                )
            )

            view = pdk.ViewState(
                latitude=float(home_lat),
                longitude=float(home_lon),
                zoom=4.5,
                pitch=0,
            )

            tooltip = {
                "html": (
                    "<div style='font-family:system-ui;font-size:13px;min-width:220px;'>"
                    "<b>{LOAD_ID}</b><br/>"
                    "<b>Route:</b> {ORIGIN_CITY} → {DESTINATION_CITY}<br/>"
                    "<b>Rate:</b> {rate_fmt} · {MILES} mi<br/>"
                    "<b>Equipment:</b> {EQUIPMENT_REQUIRED}<br/>"
                    "<hr style='margin:4px 0;border-color:#555'/>"
                    "<b>Broker:</b> {BROKER_NAME}<br/>"
                    "Credit: {CREDIT_SCORE} · Fraud: {FRAUD_RISK_LEVEL}<br/>"
                    "Match: <b>{risk_label}</b> ({score_pct})"
                    "</div>"
                ),
                "style": {
                    "backgroundColor": "#1e252f",
                    "color": "#bdc4d5",
                    "border": "1px solid #293246",
                    "borderRadius": "8px",
                    "padding": "8px 12px",
                },
            }

            deck = pdk.Deck(
                layers=layers,
                initial_view_state=view,
                tooltip=tooltip,
                map_style=None,  # Auto dark/light based on Streamlit theme
            )

            # Render — use on_select for click-to-select (Streamlit >=1.52)
            event = st.pydeck_chart(
                deck,
                use_container_width=True,
                height=520,
                on_select="rerun",
                selection_mode="single-object",
            )

            # Inline legend below map
            legend_items = "".join(
                f'<span style="display:inline-flex;align-items:center;gap:4px;margin-right:14px">'
                f'<span style="width:10px;height:10px;border-radius:50%;background:rgb({c[0]},{c[1]},{c[2]});'
                f'display:inline-block"></span>'
                f'<span style="font-size:0.75rem;color:#9fabc1">{_RISK_LABELS[k]}</span></span>'
                for k, c in _RISK_RGBA.items()
            )
            st.html(
                f'<div style="display:flex;flex-wrap:wrap;align-items:center;gap:4px;padding:6px 0">'
                f'{legend_items}'
                f'<span style="display:inline-flex;align-items:center;gap:4px;margin-right:14px">'
                f'<span style="width:10px;height:10px;border-radius:50%;background:rgb(156,91,234);'
                f'display:inline-block"></span>'
                f'<span style="font-size:0.75rem;color:#9fabc1">Driver home</span></span>'
                f'</div>'
            )

        # --- Click-to-select detail card ---
        if not filtered_df.empty and event and event.selection:
            sel_objects = event.selection.get("objects", {})
            # Look in the load-origins layer first, then try any layer
            picked = None
            for layer_id in ("load-origins",):
                if layer_id in sel_objects and sel_objects[layer_id]:
                    picked = sel_objects[layer_id][0]
                    break
            if not picked:
                for _layer_key, obj_list in sel_objects.items():
                    if obj_list:
                        picked = obj_list[0]
                        break
            if picked and "LOAD_ID" in picked:
                closest = filtered_df[filtered_df["LOAD_ID"] == picked["LOAD_ID"]]
                if not closest.empty:
                    closest = closest.iloc[0]
                    with ctrl_col:
                        fraud_c = (
                            "var(--success)" if closest["FRAUD_RISK_LEVEL"] == "LOW"
                            else "var(--warning)" if closest["FRAUD_RISK_LEVEL"] == "MEDIUM"
                            else "var(--danger)"
                        )
                        risk_c = _RISK_COLORS.get(closest["RISK_LEVEL"], "#7081a0")
                        st.html(f"""
                        <div class="neu-card" style="margin-top:12px">
                            <div style="font-weight:700;color:var(--text-header);margin-bottom:4px">{closest['LOAD_ID']}</div>
                            <div style="font-size:0.85rem;color:var(--text-primary)">
                                {closest['ORIGIN_CITY']} &rarr; {closest['DESTINATION_CITY']}
                            </div>
                            <div style="display:flex;justify-content:space-between;margin-top:8px">
                                <span style="color:var(--success);font-weight:600;font-size:1.1rem">${closest['TOTAL_RATE']:,.0f}</span>
                                <span style="font-size:0.85rem;color:var(--text-secondary)">{closest['MILES']} mi</span>
                            </div>
                            <div style="font-size:0.8rem;margin-top:8px;padding-top:8px;border-top:1px solid var(--border)">
                                <div style="color:var(--text-secondary)">Broker: {closest['BROKER_NAME']}</div>
                                <div>Credit: {closest['CREDIT_SCORE']} · Fraud: <span style="color:{fraud_c};font-weight:600">{closest['FRAUD_RISK_LEVEL']}</span></div>
                                <div style="margin-top:4px">
                                    <span style="color:{risk_c};font-weight:600">{_RISK_LABELS.get(closest['RISK_LEVEL'], '')}</span>
                                    <span style="color:var(--text-secondary)"> ({closest['RECOMMENDATION_SCORE']:.0%})</span>
                                </div>
                            </div>
                        </div>
                        """)

    # Weather alerts section
    st.html('<div class="section-header">Weather alerts</div>')
    high_risk_weather = weather_df[weather_df["WEATHER_RISK_LEVEL"] == "HIGH"]
    if len(high_risk_weather) > 0:
        alert_cols = st.columns(min(4, len(high_risk_weather)))
        for i, (_, wx) in enumerate(high_risk_weather.head(4).iterrows()):
            with alert_cols[i]:
                st.html(f"""
                <div class="neu-card-inset" style="border-left:3px solid var(--danger);">
                    <div style="font-weight:600;color:var(--text-header);font-size:0.9rem;">{wx['CITY_NAME']}</div>
                    <div style="font-size:0.8rem;color:var(--text-secondary);margin-top:4px;">
                        {wx['AVG_TEMP_F']:.0f}&deg;F &middot; Wind {wx['MAX_WIND_MPH']:.0f} mph
                    </div>
                    <div style="font-size:0.75rem;color:var(--danger-light);margin-top:4px;">HIGH RISK</div>
                </div>
                """)
    else:
        st.success("No high-risk weather conditions currently.")


# ===== TAB 2: Match Engine ===================================================
with tab_match:

    @st.cache_data(ttl=300)
    def load_recommendations():
        return run_query("""
            SELECT DRIVER_ID, LOAD_ID, RECOMMENDATION_SCORE, RISK_LEVEL,
                   ORIGIN_CITY, ORIGIN_STATE, DESTINATION_CITY, DESTINATION_STATE,
                   TOTAL_RATE, EQUIPMENT_REQUIRED, MILES,
                   BROKER_NAME, CREDIT_SCORE, FRAUD_RISK_LEVEL, COMPOSITE_RISK_SCORE
            FROM APEX_CAPITAL_DEMO.ANALYTICS.LOADSTAR_RECOMMENDATIONS_V
            ORDER BY RECOMMENDATION_SCORE DESC
        """)

    recs_df = load_recommendations()
    
    # Initialize session state for selected load
    if "selected_load" not in st.session_state:
        st.session_state.selected_load = None

    # Header controls
    ctrl_cols = st.columns([1, 1, 2])
    with ctrl_cols[0]:
        driver_ids = sorted(recs_df["DRIVER_ID"].unique())
        sel_driver = st.selectbox("Select driver", driver_ids)
    with ctrl_cols[1]:
        min_score = st.slider("Min match score", 0.0, 1.0, 0.5, 0.05)

    # Filter recommendations
    driver_recs = (
        recs_df[(recs_df["DRIVER_ID"] == sel_driver) & (recs_df["RECOMMENDATION_SCORE"] >= min_score)]
        .sort_values("RECOMMENDATION_SCORE", ascending=False)
    )

    if driver_recs.empty:
        st.warning(f"No recommendations above {min_score:.0%} for driver {sel_driver}. Try lowering the threshold.")
    else:
        # Two-column layout: cards on left, detail panel on right
        cards_col, detail_col = st.columns([2, 1])
        
        with cards_col:
            st.html(f'<div class="section-header">{len(driver_recs)} matching loads</div>')
            
            # Create clickable cards using buttons
            for idx, (_, rec) in enumerate(driver_recs.head(8).iterrows()):
                score = rec["RECOMMENDATION_SCORE"]
                sc = match_color(score)
                fraud = rec.get("FRAUD_RISK_LEVEL", "LOW")
                
                col1, col2, col3, col4, col5 = st.columns([1, 2, 2, 1, 1])
                
                with col1:
                    st.html(f"""
                    <div class="match-gauge" style="border:3px solid {sc};color:{sc};margin:4px 0;">
                        {score*100:.0f}%
                    </div>
                    """)
                with col2:
                    st.markdown(f"**{rec['LOAD_ID']}**")
                    st.caption(f"{rec['ORIGIN_CITY']} → {rec['DESTINATION_CITY']}")
                with col3:
                    st.markdown(f"**${rec['TOTAL_RATE']:,.0f}**")
                    st.caption(f"{rec.get('MILES', 'N/A')} miles")
                with col4:
                    st.caption(rec['BROKER_NAME'][:15])
                    fraud_colors = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
                    st.caption(fraud_colors.get(fraud, "⚪"))
                with col5:
                    if st.button("Select", key=f"sel_{rec['LOAD_ID']}"):
                        st.session_state.selected_load = rec.to_dict()
                        st.rerun()
                
                st.divider()
        
        with detail_col:
            st.html('<div class="section-header">Load details</div>')
            
            if st.session_state.selected_load:
                load = st.session_state.selected_load
                score = load["RECOMMENDATION_SCORE"]
                sc = match_color(score)
                
                st.html(f"""
                <div class="neu-card">
                    <div style="text-align:center;margin-bottom:16px;">
                        <div class="match-gauge" style="border:4px solid {sc};color:{sc};width:70px;height:70px;font-size:1.3rem;margin:0 auto;">
                            {score*100:.0f}%
                        </div>
                        <div style="margin-top:8px;font-size:0.8rem;color:var(--text-secondary);">Match score</div>
                    </div>
                    <div style="font-weight:700;color:var(--text-header);font-size:1.1rem;text-align:center;">
                        {load['LOAD_ID']}
                    </div>
                </div>
                """)
                
                st.html(f"""
                <div class="neu-card-inset" style="margin-top:12px;">
                    <div style="font-size:0.75rem;color:var(--text-secondary);margin-bottom:4px;">ROUTE</div>
                    <div style="color:var(--text-primary);font-size:0.9rem;">
                        {load['ORIGIN_CITY']}, {load['ORIGIN_STATE']}<br/>
                        ↓<br/>
                        {load['DESTINATION_CITY']}, {load['DESTINATION_STATE']}
                    </div>
                    <div style="margin-top:8px;color:var(--text-secondary);font-size:0.85rem;">
                        {load.get('MILES', 'N/A')} miles
                    </div>
                </div>
                """)
                
                st.html(f"""
                <div class="neu-card-inset" style="margin-top:12px;">
                    <div style="font-size:0.75rem;color:var(--text-secondary);margin-bottom:4px;">COMPENSATION</div>
                    <div style="color:var(--success);font-weight:700;font-size:1.3rem;">${load['TOTAL_RATE']:,.0f}</div>
                    <div style="color:var(--text-secondary);font-size:0.85rem;margin-top:4px;">
                        ${load['TOTAL_RATE']/max(load.get('MILES', 1), 1):,.2f}/mile
                    </div>
                </div>
                """)
                
                fraud = load.get("FRAUD_RISK_LEVEL", "LOW")
                fraud_color = {"LOW": "var(--success)", "MEDIUM": "var(--warning)", "HIGH": "var(--danger)"}.get(fraud, "var(--text-secondary)")
                st.html(f"""
                <div class="neu-card-inset" style="margin-top:12px;">
                    <div style="font-size:0.75rem;color:var(--text-secondary);margin-bottom:4px;">BROKER</div>
                    <div style="color:var(--text-header);font-weight:600;">{load['BROKER_NAME']}</div>
                    <div style="display:flex;justify-content:space-between;margin-top:8px;">
                        <span style="font-size:0.8rem;color:var(--text-secondary);">Credit: {load.get('CREDIT_SCORE', 'N/A')}</span>
                        <span style="font-size:0.8rem;color:{fraud_color};">{fraud} risk</span>
                    </div>
                </div>
                """)
                
                # Live ML Scoring
                st.markdown("---")
                if st.button("🧠 Get Live ML Score", use_container_width=True):
                    with st.spinner("Running ML inference..."):
                        # Extract numeric load ID
                        load_id_num = int(''.join(filter(str.isdigit, str(load['LOAD_ID']))) or '0')
                        live_score_df = run_query(f"""
                            SELECT APEX_CAPITAL_DEMO.ML.GET_RECOMMENDATION_SCORE(
                                {sel_driver}, {load_id_num}
                            ) AS LIVE_SCORE
                        """)
                        if len(live_score_df) > 0:
                            live_score = float(live_score_df.iloc[0]["LIVE_SCORE"])
                            live_sc = match_color(live_score)
                            st.html(f"""
                            <div class="neu-card" style="text-align:center;margin-top:8px;border:2px solid {live_sc};">
                                <div style="font-size:0.75rem;color:var(--text-secondary);margin-bottom:4px;">REAL-TIME ML SCORE</div>
                                <div style="color:{live_sc};font-weight:700;font-size:1.5rem;">{live_score*100:.1f}%</div>
                                <div style="font-size:0.7rem;color:var(--text-secondary);margin-top:4px;">
                                    via GET_RECOMMENDATION_SCORE UDF
                                </div>
                            </div>
                            """)
                
                # Action buttons
                act_col1, act_col2 = st.columns(2)
                with act_col1:
                    if st.button("✓ Accept load", use_container_width=True, type="primary"):
                        st.success(f"Load {load['LOAD_ID']} accepted!")
                with act_col2:
                    if st.button("✗ Decline", use_container_width=True):
                        st.session_state.selected_load = None
                        st.rerun()
            else:
                st.html("""
                <div class="neu-card-inset" style="text-align:center;padding:40px 20px;">
                    <div style="font-size:2rem;margin-bottom:12px;">📦</div>
                    <div style="color:var(--text-secondary);font-size:0.9rem;">
                        Select a load from the list to view details
                    </div>
                </div>
                """)


# ===== TAB 3: Broker 360 Inspector ==========================================
with tab_broker:

    @st.cache_data(ttl=300)
    def load_brokers():
        return run_query("""
            SELECT BROKER_ID, BROKER_NAME, MC_NUMBER, HQ_STATE,
                   CREDIT_SCORE, FACTORING_TYPE, TOTAL_INVOICES,
                   TOTAL_FACTORED_AMOUNT, AVG_DAYS_TO_PAY,
                   DISPUTED_INVOICES, FRAUD_RISK_LEVEL,
                   COMPOSITE_RISK_SCORE, DOUBLE_BROKER_FLAG,
                   CURRENT_WEATHER_RISK, UNIQUE_LANES,
                   PRIMARY_ORIGIN, PRIMARY_DESTINATION,
                   LANE_DENSITY, LAST_REFRESHED
            FROM APEX_CAPITAL_DEMO.ANALYTICS.BROKER_360
            ORDER BY BROKER_NAME
        """)

    brokers_df = load_brokers()

    # Broker selector
    col_sel, col_spacer = st.columns([2, 3])
    with col_sel:
        st.html('<div class="section-header">Broker lookup</div>')
        broker_names = brokers_df["BROKER_NAME"].tolist()
        sel_broker = st.selectbox("Search broker", broker_names, label_visibility="collapsed")

    broker = brokers_df[brokers_df["BROKER_NAME"] == sel_broker].iloc[0]

    # Header row — risk gauge + identity
    h_left, h_right = st.columns([1, 3])
    with h_left:
        risk_val = broker["COMPOSITE_RISK_SCORE"]
        risk_color = (
            "#1db588" if risk_val < 30
            else "#e8a317" if risk_val < 60
            else "#ef405e"
        )
        gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=float(risk_val),
                gauge=dict(
                    axis=dict(range=[0, 100], tickcolor="#70819a"),
                    bar=dict(color=risk_color),
                    bgcolor="#293246",
                    borderwidth=0,
                    steps=[
                        dict(range=[0, 30], color="rgba(29,181,136,0.1)"),
                        dict(range=[30, 60], color="rgba(232,163,23,0.1)"),
                        dict(range=[60, 100], color="rgba(211,19,47,0.1)"),
                    ],
                ),
                title=dict(text="Composite risk", font=dict(size=13, color="#9fabc1")),
                number=dict(font=dict(size=36, color=risk_color)),
            )
        )
        gauge.update_layout(
            paper_bgcolor="#191e24",
            plot_bgcolor="#1e252f",
            height=200,
            margin=dict(l=20, r=20, t=40, b=10),
            font=dict(family="Inter"),
        )
        st.plotly_chart(gauge, use_container_width=True)

    with h_right:
        fraud_badge = risk_badge(broker["FRAUD_RISK_LEVEL"])
        double_flag = (
            '<span class="risk-badge risk-critical">DOUBLE BROKER FLAG</span>'
            if broker["DOUBLE_BROKER_FLAG"]
            else ""
        )
        header_html = f"""
        <div class="neu-card">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <div style="font-size:1.3rem;font-weight:700;color:var(--text-header);">{broker['BROKER_NAME']}</div>
                    <div style="font-size:0.85rem;color:var(--text-secondary);margin-top:4px;">
                        MC #{broker['MC_NUMBER']} &middot; {broker['HQ_STATE']} &middot; {broker['FACTORING_TYPE']}
                    </div>
                </div>
                <div style="text-align:right;">{fraud_badge} {double_flag}</div>
            </div>
            <div style="margin-top:12px;font-size:0.8rem;color:var(--text-secondary);">
                Primary lane: {broker.get('PRIMARY_ORIGIN', 'N/A')} &rarr; {broker.get('PRIMARY_DESTINATION', 'N/A')}
                &middot; {broker.get('UNIQUE_LANES', 0)} unique lanes
                &middot; Last refreshed: {str(broker.get('LAST_REFRESHED', 'N/A'))[:19]}
            </div>
        </div>
        """
        st.html(header_html)

    # Stat cards
    stat_cols = st.columns(5)
    stats = [
        ("Credit score", f"{broker['CREDIT_SCORE']:.0f}", "#5999f8"),
        ("Avg days to pay", f"{broker['AVG_DAYS_TO_PAY']:.1f}", "var(--text-header)"),
        ("Total invoices", f"{broker['TOTAL_INVOICES']:,}", "var(--text-header)"),
        ("Disputed", f"{broker['DISPUTED_INVOICES']}", "var(--danger-light)" if broker["DISPUTED_INVOICES"] > 5 else "var(--text-header)"),
        ("Total factored", f"${broker['TOTAL_FACTORED_AMOUNT']:,.0f}", "var(--success)"),
    ]
    for i, (label, val, color) in enumerate(stats):
        with stat_cols[i]:
            st.html(stat_card(label, val, color))

    # Weather + additional context
    wx_col, agent_col = st.columns([1, 2])

    with wx_col:
        st.html('<div class="section-header">Current conditions</div>')
        wx_risk = broker.get("CURRENT_WEATHER_RISK", "N/A")
        if wx_risk is None or str(wx_risk).upper() in ("NONE", "NAN", ""):
            wx_risk = "N/A"
        wx_badge = risk_badge(wx_risk)
        st.html(
            f'<div class="neu-card-inset">'
            f'<div style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:8px;">Weather risk</div>'
            f'<div>{wx_badge}</div>'
            f'<div style="margin-top:12px;font-size:0.85rem;color:var(--text-secondary);">'
            f'Lane density: {broker.get("LANE_DENSITY", "N/A")}</div>'
            f"</div>"
        )

    with agent_col:
        st.html('<div class="section-header">Ask the broker agent</div>')

        if "agent_messages" not in st.session_state:
            st.session_state.agent_messages = []

        for msg in st.session_state.agent_messages:
            avatar = "👤" if msg["role"] == "user" else "🤖"
            with st.chat_message(msg["role"], avatar=avatar):
                # Show thinking in expander for assistant messages (if available)
                if msg["role"] == "assistant" and msg.get("thinking_steps"):
                    with st.expander("🧠 View agent reasoning", expanded=False):
                        st.html(render_thinking_html(msg["thinking_steps"]))
                st.markdown(msg["content"])

        if prompt := st.chat_input(
            f"Ask about {sel_broker}...", key="broker_chat"
        ):
            st.session_state.agent_messages.append(
                {"role": "user", "content": prompt}
            )
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

            with st.chat_message("assistant", avatar="🤖"):
                # Create expander immediately - visible from start
                expander_container = st.container()
                response_placeholder = st.empty()
                
                # Chronological list of steps (preserves order as they happen)
                steps = []  # List of {"category": ..., "text": ..., "reasoning": ...}
                prev_reasoning_len = 0  # Track how much reasoning we've already assigned
                full_response = ""
                
                # Create expander and placeholder INSIDE it for dynamic updates
                with expander_container:
                    expander = st.expander("🧠 Agent reasoning", expanded=True)
                    with expander:
                        thinking_placeholder = st.empty()
                        init_html = render_thinking_html([])
                        thinking_placeholder.html(init_html)
                
                for mode, text in call_cortex_agent_streaming(prompt, broker_context=sel_broker):
                    if mode == "status":
                        # Store step with category in chronological order
                        category = categorize_status(text)
                        # Only add if not a duplicate of the last step
                        if not steps or steps[-1].get("text") != text:
                            steps.append({"category": category, "text": text, "reasoning": ""})
                        # Update display
                        thinking_placeholder.html(render_thinking_html(steps))
                    elif mode == "sql":
                        # SQL query - add as special category with code block
                        steps.append({"category": "sql", "text": text, "reasoning": ""})
                        thinking_placeholder.html(render_thinking_html(steps))
                    elif mode == "thinking":
                        # Distribute new reasoning tokens to the most recent step
                        new_chunk = text[prev_reasoning_len:]
                        prev_reasoning_len = len(text)
                        if steps and new_chunk:
                            steps[-1]["reasoning"] += new_chunk
                        thinking_placeholder.html(render_thinking_html(steps))
                    else:  # mode == "answer"
                        full_response = text
                        response_placeholder.markdown(full_response + " ▌")
                
                # Redistribute reasoning: if all reasoning ended up on the last
                # step, spread it evenly across steps that have none.
                non_sql_steps = [s for s in steps if s["category"] != "sql"]
                steps_with_reasoning = [s for s in non_sql_steps if s["reasoning"]]
                steps_without = [s for s in non_sql_steps if not s["reasoning"]]
                if len(steps_with_reasoning) == 1 and steps_without:
                    blob = steps_with_reasoning[0]["reasoning"]
                    # Split on double-newlines or long single paragraphs
                    chunks = [c.strip() for c in _re.split(r'\n{2,}', blob) if c.strip()]
                    if len(chunks) >= len(non_sql_steps):
                        # Distribute chunks round-robin across all non-sql steps
                        per_step = max(1, len(chunks) // len(non_sql_steps))
                        for i, s in enumerate(non_sql_steps):
                            start = i * per_step
                            end = start + per_step if i < len(non_sql_steps) - 1 else len(chunks)
                            s["reasoning"] = "\n\n".join(chunks[start:end])
                
                # Final render
                thinking_placeholder.html(render_thinking_html(steps))
                response_placeholder.markdown(full_response)

            st.session_state.agent_messages.append(
                {"role": "assistant", "content": full_response, "thinking_steps": steps}
            )

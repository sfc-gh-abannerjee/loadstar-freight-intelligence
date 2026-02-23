"""
LoadStar Commander — Freight intelligence dashboard.
Runs on Snowflake Container Runtime (SPCS).
"""

import json
import os

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
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
    transition: transform 0.2s ease;
    display: inline-block;
}
[data-testid="stExpander"][open] summary::before {
    content: "▼";
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
                
                # Status events (Planning, Executing tool, etc.)
                if event_type == "response.status":
                    status = parsed.get("status", "")
                    message = parsed.get("message", "")
                    if message and message != last_status:
                        last_status = message
                        yield ("status", message)
                
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
                
                # Tool result (contains SQL queries and other tool outputs)
                elif event_type == "response.tool_result":
                    # Try to extract SQL from tool results
                    tool_result = parsed.get("tool_result", parsed)
                    if isinstance(tool_result, dict):
                        # Check for SQL in various locations
                        sql = tool_result.get("sql", "")
                        if not sql:
                            content = tool_result.get("content", "")
                            if isinstance(content, str) and content.strip().upper().startswith(("SELECT", "WITH", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP")):
                                sql = content
                        if sql:
                            yield ("sql", sql.strip())
                
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


def render_thinking_html(steps: list, reasoning: str = "") -> str:
    """Render thinking steps as a chronological timeline with styled items."""
    html_parts = []
    
    # Render steps in chronological order
    for step in steps:
        category = step.get("category", "planning")
        text = step.get("text", "")
        
        if category == "planning":
            icon = "✓"
            color = "#1a6ce7"
            html_parts.append(f'''
            <div class="step-item" style="border-left: 3px solid {color}; padding-left: 12px; margin-bottom: 8px;">
                <span class="icon">{icon}</span> {text}
            </div>
            ''')
        elif category == "sql":
            # SQL queries get a code block
            html_parts.append(f'''
            <div class="step-item" style="border-left: 3px solid #9c5bea; padding-left: 12px; margin-bottom: 12px;">
                <div style="font-size: 0.75rem; color: #9c5bea; font-weight: 600; margin-bottom: 6px;">📊 SQL Query</div>
                <pre style="background: #1a1d24; border-radius: 6px; padding: 10px 12px; margin: 0; overflow-x: auto; font-size: 0.8rem; line-height: 1.4;"><code style="color: #e0e6ed; font-family: 'SF Mono', Monaco, Consolas, monospace;">{text}</code></pre>
            </div>
            ''')
        else:  # tool
            icon = "⚡"
            color = "#e8a317"
            html_parts.append(f'''
            <div class="step-item" style="border-left: 3px solid {color}; padding-left: 12px; margin-bottom: 8px;">
                <span class="icon">{icon}</span> {text}
            </div>
            ''')
    
    # Reasoning section at the end (if present)
    if reasoning:
        # Truncate very long reasoning for display
        if len(reasoning) > 800:
            reasoning = reasoning[:800] + "..."
        html_parts.append(f'''
        <div class="thinking-section reasoning">
            <div class="section-label">🧠 Agent Reasoning</div>
            <div class="reasoning-text">{reasoning}</div>
        </div>
        ''')
    
    return "".join(html_parts) if html_parts else '<div class="thinking-section"><em>⏳ Processing...</em></div>'


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
        carriers = run_query("""
            SELECT CARRIER_NAME, HOME_LATITUDE AS LAT, HOME_LONGITUDE AS LON,
                   EQUIPMENT_TYPE::STRING AS EQUIPMENT, STATUS, FLEET_SIZE
            FROM APEX_CAPITAL_DEMO.RAW.CARRIER_PROFILES
            WHERE HOME_LATITUDE IS NOT NULL
        """)
        loads = run_query("""
            SELECT LOAD_ID, ORIGIN_CITY::STRING AS ORIGIN_CITY,
                   ORIGIN_STATE::STRING AS ORIGIN_STATE,
                   ORIGIN_LATITUDE AS O_LAT, ORIGIN_LONGITUDE AS O_LON,
                   DESTINATION_CITY::STRING AS DEST_CITY,
                   DESTINATION_STATE::STRING AS DEST_STATE,
                   TOTAL_RATE, STATUS,
                   EQUIPMENT_REQUIRED::STRING AS EQUIPMENT
            FROM APEX_CAPITAL_DEMO.RAW.LOAD_POSTINGS
            WHERE ORIGIN_LATITUDE IS NOT NULL AND STATUS = 'AVAILABLE'
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
        return carriers, loads, weather

    carriers_df, loads_df, weather_df = load_map_data()

    # KPI row at top
    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        st.html(stat_card("Active carriers", str(len(carriers_df))))
    with kpi_cols[1]:
        st.html(stat_card("Available loads", str(len(loads_df))))
    with kpi_cols[2]:
        high_risk_ct = weather_df.loc[
            weather_df["WEATHER_RISK_LEVEL"].isin(["HIGH"]), "CITY_NAME"
        ].nunique()
        st.html(stat_card("High-risk cities", str(high_risk_ct), "var(--danger-light)"))
    with kpi_cols[3]:
        avg_rate = f"${loads_df['TOTAL_RATE'].mean():,.0f}" if len(loads_df) else "$0"
        st.html(stat_card("Avg load rate", avg_rate, "var(--success)"))

    # Two-column layout: map on left, controls on right
    map_col, ctrl_col = st.columns([3, 1])

    with ctrl_col:
        st.html('<div class="section-header">Find & Select</div>')
        
        view_mode = st.radio("View", ["Loads", "Carriers"], horizontal=True, label_visibility="collapsed")
        
        if view_mode == "Loads":
            # Equipment filter
            equip_opts = ["All equipment"] + sorted(loads_df["EQUIPMENT"].dropna().unique().tolist())
            sel_equip = st.selectbox("Equipment", equip_opts, label_visibility="collapsed")
            
            display_df = loads_df.copy()
            if sel_equip != "All equipment":
                display_df = display_df[display_df["EQUIPMENT"] == sel_equip]
            
            # Searchable selectbox instead of radio list
            load_options = display_df.apply(
                lambda r: f"{r['LOAD_ID']} — {r['ORIGIN_CITY']} → {r['DEST_CITY']}",
                axis=1
            ).tolist()
            
            if load_options:
                selected_item = st.selectbox(
                    "Select load",
                    load_options,
                    label_visibility="collapsed",
                    placeholder="Search loads...",
                )
                selected_idx = load_options.index(selected_item)
                selected_row = display_df.iloc[selected_idx]
                center_lat, center_lon = selected_row["O_LAT"], selected_row["O_LON"]
                zoom_level = 8
                
                # Compact detail card
                st.html(f"""
                <div class="neu-card">
                    <div style="font-weight:700;color:var(--text-header);margin-bottom:6px;">{selected_row['LOAD_ID']}</div>
                    <div style="font-size:0.85rem;color:var(--text-primary);">
                        {selected_row['ORIGIN_CITY']}, {selected_row['ORIGIN_STATE']}<br/>
                        → {selected_row['DEST_CITY']}, {selected_row['DEST_STATE']}
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-top:10px;">
                        <span style="color:var(--success);font-weight:600;font-size:1.2rem;">${selected_row['TOTAL_RATE']:,.0f}</span>
                        <span style="color:var(--text-secondary);font-size:0.85rem;">{selected_row['EQUIPMENT']}</span>
                    </div>
                </div>
                """)
            else:
                center_lat, center_lon, zoom_level = 32.5, -99.5, 5.5
                selected_row = None
        else:
            # Carriers view
            status_opts = ["All statuses"] + sorted(carriers_df["STATUS"].dropna().unique().tolist())
            sel_status = st.selectbox("Status", status_opts, label_visibility="collapsed")
            
            display_df = carriers_df.copy()
            if sel_status != "All statuses":
                display_df = display_df[display_df["STATUS"] == sel_status]
            
            carrier_options = display_df.apply(
                lambda r: f"{r['CARRIER_NAME']} ({r['EQUIPMENT']})",
                axis=1
            ).tolist()
            
            if carrier_options:
                selected_item = st.selectbox(
                    "Select carrier",
                    carrier_options,
                    label_visibility="collapsed",
                    placeholder="Search carriers...",
                )
                selected_idx = carrier_options.index(selected_item)
                selected_row = display_df.iloc[selected_idx]
                center_lat, center_lon = selected_row["LAT"], selected_row["LON"]
                zoom_level = 9
                
                status_color = "var(--success)" if selected_row["STATUS"] == "ACTIVE" else "var(--text-secondary)"
                st.html(f"""
                <div class="neu-card">
                    <div style="font-weight:700;color:var(--text-header);margin-bottom:6px;">{selected_row['CARRIER_NAME']}</div>
                    <div style="font-size:0.85rem;color:var(--text-primary);">Equipment: {selected_row['EQUIPMENT']}</div>
                    <div style="display:flex;justify-content:space-between;margin-top:10px;">
                        <span style="color:{status_color};font-weight:600;">{selected_row['STATUS']}</span>
                        <span style="color:var(--text-secondary);font-size:0.85rem;">{selected_row['FLEET_SIZE']} trucks</span>
                    </div>
                </div>
                """)
            else:
                center_lat, center_lon, zoom_level = 32.5, -99.5, 5.5
                selected_row = None

    with map_col:
        # Build map layers
        view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=zoom_level, pitch=0)
        
        layers = []
        
        if view_mode == "Loads":
            # All loads as small dots
            loads_layer = pdk.Layer(
                "ScatterplotLayer",
                data=loads_df,
                get_position=["O_LON", "O_LAT"],
                get_fill_color=[29, 181, 136, 180],
                get_radius=800,
                radius_min_pixels=4,
                radius_max_pixels=12,
                pickable=True,
                auto_highlight=True,
            )
            layers.append(loads_layer)
            
            # Highlight selected load
            if selected_row is not None:
                highlight_df = pd.DataFrame([{
                    "LAT": selected_row["O_LAT"],
                    "LON": selected_row["O_LON"],
                    "LOAD_ID": selected_row["LOAD_ID"],
                }])
                highlight_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=highlight_df,
                    get_position=["LON", "LAT"],
                    get_fill_color=[255, 215, 0, 255],
                    get_radius=2000,
                    radius_min_pixels=8,
                    radius_max_pixels=20,
                    pickable=False,
                )
                layers.append(highlight_layer)
            
            tooltip_html = "<b>{LOAD_ID}</b><br/>{ORIGIN_CITY} → {DEST_CITY}<br/>Rate: ${TOTAL_RATE}<br/>Equipment: {EQUIPMENT}"
        else:
            # All carriers as small dots
            carrier_map = carriers_df.copy()
            carrier_map["COLOR"] = carrier_map.apply(
                lambda r: [26, 108, 231, 200] if r["STATUS"] == "ACTIVE" else [112, 129, 154, 140],
                axis=1,
            )
            carriers_layer = pdk.Layer(
                "ScatterplotLayer",
                data=carrier_map,
                get_position=["LON", "LAT"],
                get_fill_color="COLOR",
                get_radius=800,
                radius_min_pixels=4,
                radius_max_pixels=12,
                pickable=True,
                auto_highlight=True,
            )
            layers.append(carriers_layer)
            
            # Highlight selected carrier
            if selected_row is not None:
                highlight_df = pd.DataFrame([{
                    "LAT": selected_row["LAT"],
                    "LON": selected_row["LON"],
                    "CARRIER_NAME": selected_row["CARRIER_NAME"],
                }])
                highlight_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=highlight_df,
                    get_position=["LON", "LAT"],
                    get_fill_color=[255, 215, 0, 255],
                    get_radius=2000,
                    radius_min_pixels=8,
                    radius_max_pixels=20,
                    pickable=False,
                )
                layers.append(highlight_layer)
            
            tooltip_html = "<b>{CARRIER_NAME}</b><br/>Equipment: {EQUIPMENT}<br/>Fleet: {FLEET_SIZE}<br/>Status: {STATUS}"

        deck = pdk.Deck(
            layers=layers,
            initial_view_state=view,
            map_style="dark_no_labels",
            tooltip={
                "html": tooltip_html,
                "style": {
                    "backgroundColor": "#1e252f",
                    "color": "#bdc4d5",
                    "border": "1px solid #293246",
                    "border-radius": "8px",
                    "padding": "8px",
                },
            },
        )
        st.pydeck_chart(deck, use_container_width=True, height=520)

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
                        {wx['AVG_TEMP_F']:.0f}°F · Wind {wx['MAX_WIND_MPH']:.0f} mph
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
                if msg["role"] == "assistant" and msg.get("thinking"):
                    with st.expander("🧠 View agent reasoning", expanded=False):
                        st.html(msg["thinking"])
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
                steps = []  # List of {"category": "planning"|"tool", "text": "..."}
                reasoning = ""
                full_response = ""
                
                # Create expander and placeholder INSIDE it for dynamic updates
                with expander_container:
                    expander = st.expander("🧠 Agent reasoning", expanded=True)
                    with expander:
                        thinking_placeholder = st.empty()
                        thinking_placeholder.html('<div class="thinking-section"><em>⏳ Starting...</em></div>')
                
                for mode, text in call_cortex_agent_streaming(prompt, broker_context=sel_broker):
                    if mode == "status":
                        # Store step with category in chronological order
                        category = categorize_status(text)
                        # Only add if not a duplicate of the last step
                        if not steps or steps[-1].get("text") != text:
                            steps.append({"category": category, "text": text})
                        # Update display with chronological timeline
                        thinking_placeholder.html(render_thinking_html(steps, reasoning))
                    elif mode == "sql":
                        # SQL query - add as special category with code block
                        steps.append({"category": "sql", "text": text})
                        thinking_placeholder.html(render_thinking_html(steps, reasoning))
                    elif mode == "thinking":
                        # Thinking text is already accumulated, just keep latest
                        reasoning = text
                        # Update display with chronological timeline (includes reasoning)
                        thinking_placeholder.html(render_thinking_html(steps, reasoning))
                    else:  # mode == "answer"
                        full_response = text
                        response_placeholder.markdown(full_response + " ▌")
                
                # Final render: update expander with complete content
                thinking_placeholder.html(render_thinking_html(steps, reasoning))
                response_placeholder.markdown(full_response)
                
                # Store structured thinking for history display
                thinking_text = render_thinking_html(steps, reasoning)

            st.session_state.agent_messages.append(
                {"role": "assistant", "content": full_response, "thinking": thinking_text}
            )

import streamlit as st
import os
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv
from streamlit_agraph import agraph, Node, Edge, Config
import requests

# Load environment
load_dotenv()

API_BASE = os.getenv("LMS_API_BASE", "http://127.0.0.1:8000")

# Page Config
st.set_page_config(
    page_title="⚗️ The Lore Oracle",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# HAUNTING MACHINE AESTHETIC - CSS
# ==========================================
st.markdown("""
<style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap');
    
    /* Root variables - Haunting Machine palette */
    :root {
        --bg-deep: #0a0d0a;
        --bg-surface: #0f1410;
        --bg-elevated: #141a16;
        --phosphor-green: #39ff14;
        --phosphor-dim: #2eb810;
        --phosphor-glow: rgba(57, 255, 20, 0.15);
        --amber-warning: #ffb000;
        --blood-red: #ff2e2e;
        --text-primary: #c8e6c9;
        --text-secondary: #81c784;
        --text-muted: #4a6b4a;
        --border-color: #1e3d1e;
        --border-glow: #2eb81033;
    }
    
    /* Main app background */
    .stApp {
        background: linear-gradient(180deg, var(--bg-deep) 0%, #0d120d 50%, var(--bg-deep) 100%);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-deep) 100%);
        border-right: 1px solid var(--border-color);
    }
    
    [data-testid="stSidebar"] .stMarkdown h1 {
        font-family: 'Cinzel', serif !important;
        color: var(--phosphor-green) !important;
        text-shadow: 0 0 20px var(--phosphor-glow), 0 0 40px var(--phosphor-glow);
        letter-spacing: 0.1em;
        text-align: center;
    }
    
    /* Main content headers */
    h1, h2, h3 {
        font-family: 'Cinzel', serif !important;
        color: var(--text-primary) !important;
        letter-spacing: 0.05em;
    }
    
    h1 {
        color: var(--phosphor-green) !important;
        text-shadow: 0 0 30px var(--phosphor-glow);
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 0.5rem;
    }
    
    h2 {
        color: var(--phosphor-dim) !important;
    }
    
    /* Body text */
    p, span, label, .stMarkdown {
        font-family: 'Crimson Text', serif !important;
        color: var(--text-primary) !important;
    }
    
    /* Monospace elements */
    code, pre, .stCode {
        font-family: 'JetBrains Mono', monospace !important;
        background: var(--bg-elevated) !important;
        border: 1px solid var(--border-color) !important;
    }
    
    /* Chat messages */
    [data-testid="stChatMessage"] {
        background: var(--bg-elevated) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 4px !important;
        padding: 1rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* User messages - slightly different */
    [data-testid="stChatMessage"][data-testid*="user"] {
        border-left: 3px solid var(--text-muted) !important;
    }
    
    /* Assistant messages - oracle glow */
    [data-testid="stChatMessage"]:not([data-testid*="user"]) {
        border-left: 3px solid var(--phosphor-dim) !important;
        box-shadow: inset 0 0 20px var(--phosphor-glow);
    }
    
    /* Chat input */
    [data-testid="stChatInput"] {
        background: var(--bg-elevated) !important;
        border: 1px solid var(--border-color) !important;
    }
    
    [data-testid="stChatInput"] input {
        font-family: 'Crimson Text', serif !important;
        color: var(--text-primary) !important;
        background: transparent !important;
    }
    
    [data-testid="stChatInput"] input::placeholder {
        color: var(--text-muted) !important;
        font-style: italic;
    }
    
    /* Text area */
    .stTextArea textarea {
        font-family: 'Crimson Text', serif !important;
        background: var(--bg-elevated) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 4px !important;
    }
    
    .stTextArea textarea:focus {
        border-color: var(--phosphor-dim) !important;
        box-shadow: 0 0 10px var(--phosphor-glow) !important;
    }
    
    /* Buttons */
    .stButton > button {
        font-family: 'Cinzel', serif !important;
        background: linear-gradient(180deg, var(--bg-elevated) 0%, var(--bg-surface) 100%) !important;
        color: var(--phosphor-green) !important;
        border: 1px solid var(--phosphor-dim) !important;
        border-radius: 4px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        box-shadow: 0 0 20px var(--phosphor-glow), inset 0 0 20px var(--phosphor-glow) !important;
        transform: translateY(-1px) !important;
    }
    
    .stButton > button[kind="primary"] {
        background: linear-gradient(180deg, var(--phosphor-dim) 0%, #1a6b10 100%) !important;
        color: var(--bg-deep) !important;
        font-weight: 600 !important;
    }
    
    /* Radio buttons */
    .stRadio > div {
        background: var(--bg-elevated) !important;
        border-radius: 4px !important;
        padding: 0.5rem !important;
        border: 1px solid var(--border-color) !important;
    }
    
    .stRadio label {
        font-family: 'Crimson Text', serif !important;
        color: var(--text-secondary) !important;
    }
    
    /* Divider */
    hr {
        border-color: var(--border-color) !important;
        opacity: 0.5 !important;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        font-family: 'Cinzel', serif !important;
        background: var(--bg-elevated) !important;
        border: 1px solid var(--border-color) !important;
        color: var(--text-primary) !important;
    }
    
    .streamlit-expanderContent {
        background: var(--bg-surface) !important;
        border: 1px solid var(--border-color) !important;
        border-top: none !important;
    }
    
    /* Success/Error/Warning/Info boxes */
    .stSuccess {
        background: rgba(46, 184, 16, 0.1) !important;
        border: 1px solid var(--phosphor-dim) !important;
        color: var(--phosphor-green) !important;
    }
    
    .stError {
        background: rgba(255, 46, 46, 0.1) !important;
        border: 1px solid var(--blood-red) !important;
        color: #ff6b6b !important;
    }
    
    .stWarning {
        background: rgba(255, 176, 0, 0.1) !important;
        border: 1px solid var(--amber-warning) !important;
        color: var(--amber-warning) !important;
    }
    
    .stInfo {
        background: rgba(57, 255, 20, 0.05) !important;
        border: 1px solid var(--text-muted) !important;
        color: var(--text-secondary) !important;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: var(--phosphor-green) transparent transparent transparent !important;
    }
    
    /* Caption text */
    .stCaption, small {
        color: var(--text-muted) !important;
        font-family: 'Crimson Text', serif !important;
        font-style: italic !important;
    }
    
    /* Metrics */
    [data-testid="stMetric"] {
        background: var(--bg-elevated) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 4px !important;
        padding: 1rem !important;
    }
    
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        color: var(--phosphor-green) !important;
        text-shadow: 0 0 10px var(--phosphor-glow);
    }
    
    [data-testid="stMetricLabel"] {
        font-family: 'Cinzel', serif !important;
        color: var(--text-secondary) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        font-size: 0.75rem !important;
    }
    
    /* Columns spacing */
    [data-testid="column"] {
        padding: 0.5rem !important;
    }
    
    /* Custom status classes */
    .oracle-status {
        font-family: 'JetBrains Mono', monospace;
        padding: 0.5rem 1rem;
        border-radius: 4px;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .status-connected {
        background: rgba(46, 184, 16, 0.15);
        border: 1px solid var(--phosphor-dim);
        color: var(--phosphor-green);
        text-shadow: 0 0 10px var(--phosphor-glow);
    }
    
    .status-disconnected {
        background: rgba(255, 46, 46, 0.15);
        border: 1px solid var(--blood-red);
        color: var(--blood-red);
    }
    
    /* Scanline effect overlay (subtle) */
    .stApp::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        background: repeating-linear-gradient(
            0deg,
            rgba(0, 0, 0, 0.03),
            rgba(0, 0, 0, 0.03) 1px,
            transparent 1px,
            transparent 2px
        );
        z-index: 1000;
    }
    
    /* Contradiction severity badges */
    .severity-high {
        color: var(--blood-red);
        font-weight: bold;
        text-shadow: 0 0 8px rgba(255, 46, 46, 0.5);
    }
    
    .severity-medium {
        color: var(--amber-warning);
        font-weight: bold;
    }
    
    .severity-low {
        color: var(--text-secondary);
    }
    
    /* Oracle quote styling */
    .oracle-quote {
        font-family: 'Crimson Text', serif;
        font-style: italic;
        color: var(--text-muted);
        text-align: center;
        padding: 1rem;
        border-left: 2px solid var(--border-color);
        border-right: 2px solid var(--border-color);
        margin: 1rem 0;
    }
    
    /* File uploader - Drop Zone styling */
    [data-testid="stFileUploader"] {
        background: var(--bg-elevated) !important;
        border: 2px dashed var(--phosphor-dim) !important;
        border-radius: 8px !important;
        padding: 2rem !important;
        transition: all 0.3s ease !important;
    }
    
    [data-testid="stFileUploader"]:hover {
        border-color: var(--phosphor-green) !important;
        box-shadow: 0 0 20px var(--phosphor-glow), inset 0 0 30px var(--phosphor-glow) !important;
    }
    
    [data-testid="stFileUploader"] section {
        padding: 1rem !important;
    }
    
    [data-testid="stFileUploader"] button {
        background: linear-gradient(180deg, var(--phosphor-dim) 0%, #1a6b10 100%) !important;
        color: var(--bg-deep) !important;
        font-family: 'Cinzel', serif !important;
        font-weight: 600 !important;
        border: none !important;
    }
    
    /* Upload zone custom styling */
    .upload-zone {
        background: linear-gradient(135deg, var(--bg-elevated) 0%, var(--bg-surface) 100%);
        border: 2px dashed var(--phosphor-dim);
        border-radius: 12px;
        padding: 3rem 2rem;
        text-align: center;
        margin: 1rem 0;
        transition: all 0.3s ease;
    }
    
    .upload-zone:hover {
        border-color: var(--phosphor-green);
        box-shadow: 0 0 30px var(--phosphor-glow);
    }
    
    .upload-zone-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
        filter: drop-shadow(0 0 10px var(--phosphor-glow));
    }
    
    .upload-zone-title {
        font-family: 'Cinzel', serif;
        font-size: 1.5rem;
        color: var(--phosphor-green);
        margin-bottom: 0.5rem;
        text-shadow: 0 0 10px var(--phosphor-glow);
    }
    
    .upload-zone-subtitle {
        font-family: 'Crimson Text', serif;
        color: var(--text-muted);
        font-style: italic;
    }
    
    /* Extraction results */
    .extraction-result {
        background: var(--bg-elevated);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    .entity-tag {
        display: inline-block;
        background: var(--bg-surface);
        border: 1px solid var(--phosphor-dim);
        border-radius: 4px;
        padding: 0.25rem 0.5rem;
        margin: 0.25rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: var(--phosphor-green);
    }
    
    .relationship-tag {
        display: inline-block;
        background: var(--bg-surface);
        border: 1px solid var(--amber-warning);
        border-radius: 4px;
        padding: 0.25rem 0.5rem;
        margin: 0.25rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: var(--amber-warning);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# SIMPLE API HELPERS
# ==========================================

def api_get(path: str, params: dict | None = None, timeout: int = 10):
    url = f"{API_BASE}{path}"
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, payload: dict | None = None, timeout: int = 30):
    url = f"{API_BASE}{path}"
    resp = requests.post(url, json=payload or {}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# ==========================================
# SESSION STATE
# ==========================================

if "messages" not in st.session_state:
    st.session_state.messages = []
if "audit_result" not in st.session_state:
    st.session_state.audit_result = None
if "ingestion_results" not in st.session_state:
    st.session_state.ingestion_results = None
if "ingestion_errors" not in st.session_state:
    st.session_state.ingestion_errors = None
if "ingestion_totals" not in st.session_state:
    st.session_state.ingestion_totals = None

# AIRpg state
if "airpg_session_id" not in st.session_state:
    st.session_state.airpg_session_id = None
if "airpg_history" not in st.session_state:
    st.session_state.airpg_history = []
if "airpg_session_0_complete" not in st.session_state:
    st.session_state.airpg_session_0_complete = False
if "airpg_session_0_answers" not in st.session_state:
    st.session_state.airpg_session_0_answers = {}
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = "🔮 Query The Oracle"

# ==========================================
# BACKEND CONNECTION STATUS (via /health)
# ==========================================

try:
    health = api_get("/health", timeout=5)
    is_connected = health.get("status") in ("healthy", "degraded")
    connection_error = None if is_connected else str(health)
except Exception as e:
    is_connected = False
    connection_error = str(e)

# ==========================================
# SIDEBAR - The Oracle's Sanctum
# ==========================================
with st.sidebar:
    st.markdown("# ⚗️ THE ORACLE")
    st.caption("*Keeper of Ancient Lore*")

    st.divider()

    # Connection Status
    if is_connected:
        st.markdown("""
        <div class="oracle-status status-connected">
            ◉ ORACLE AWAKENED
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="oracle-status status-disconnected">
            ◎ ORACLE DORMANT
        </div>
        """, unsafe_allow_html=True)
        if connection_error:
            st.error(f"Connection failed: {connection_error}")

    st.divider()

    # Play AIRpg - Prominent Button
    if st.button("⚔️ PLAY AIRpg", type="primary", use_container_width=True):
        st.session_state.selected_mode = "⚔️ Play AIRpg"
        st.rerun()

    # Session Controls - New / Continue
    sess_col1, sess_col2 = st.columns(2)
    with sess_col1:
        if st.button("🔄 New", help="Start new session", use_container_width=True, key="sidebar_new"):
            st.session_state.airpg_session_id = None
            st.session_state.airpg_history = []
            st.session_state.airpg_session_0_complete = False
            st.session_state.airpg_session_0_answers = {}
            st.session_state.selected_mode = "⚔️ Play AIRpg"
            st.rerun()
    with sess_col2:
        if st.button("▶️ Continue", help="Resume last session", use_container_width=True, key="sidebar_continue"):
            if is_connected:
                try:
                    data = api_get("/airpg/session/latest")
                    if data:
                        st.session_state.airpg_session_id = data["session_id"]
                        st.session_state.airpg_session_0_answers = {
                            "setting": data.get("setting", ""),
                            "character": data.get("character", ""),
                            "tone": data.get("tone", ""),
                        }
                        st.session_state.airpg_session_0_complete = data.get("session_0_complete", False)
                        history_raw = data.get("history") or "[]"
                        st.session_state.airpg_history = json.loads(history_raw)
                        st.session_state.selected_mode = "⚔️ Play AIRpg"
                        st.rerun()
                    else:
                        st.warning("No saved sessions")
                except Exception:
                    st.error("Load failed")

    # Save Slots
    if is_connected:
        st.markdown("**💾 Save Slots:**")
        slot_data = {}
        try:
            slots = api_get("/airpg/slots")
            for s in slots or []:
                slot_data[s["slot"]] = s
        except Exception:
            pass

        for slot_num in [1, 2, 3]:
            slot_info = slot_data.get(slot_num)
            col_load, col_save = st.columns([3, 1])

            with col_load:
                if slot_info:
                    setting_preview = (slot_info.get("setting") or "?")[:15]
                    label = f"Slot {slot_num}: {setting_preview}... ({slot_info.get('turns') or 0}t)"
                else:
                    label = f"Slot {slot_num}: Empty"

                if st.button(label, key=f"load_slot_{slot_num}", use_container_width=True, disabled=not slot_info):
                    try:
                        data = api_get(f"/airpg/slot/{slot_num}")
                        st.session_state.airpg_session_id = data["session_id"]
                        st.session_state.airpg_session_0_answers = {
                            "setting": data.get("setting", ""),
                            "character": data.get("character", ""),
                            "tone": data.get("tone", ""),
                        }
                        st.session_state.airpg_session_0_complete = data.get("session_0_complete", False)
                        history_raw = data.get("history") or "[]"
                        st.session_state.airpg_history = json.loads(history_raw)
                        st.session_state.selected_mode = "⚔️ Play AIRpg"
                        st.rerun()
                    except Exception:
                        st.error("Load failed")

            with col_save:
                if st.button("💾", key=f"save_slot_{slot_num}", help=f"Save to slot {slot_num}"):
                    if st.session_state.get("airpg_session_id") and st.session_state.get("airpg_history"):
                        try:
                            payload = {
                                "session_id": st.session_state.airpg_session_id,
                                "session_0_answers": st.session_state.airpg_session_0_answers,
                                "session_0_complete": st.session_state.airpg_session_0_complete,
                                "history": st.session_state.airpg_history,
                            }
                            api_post(f"/airpg/slot/{slot_num}", payload)
                            st.success(f"Slot {slot_num} ✓")
                            st.rerun()
                        except Exception:
                            st.error("Save failed")
                    else:
                        st.warning("Nothing to save")

    st.markdown("")  # Spacing

    # Mode Selection - Other modes
    st.markdown("### 📜 Consult The Archives")
    other_modes = ["🔮 Query The Oracle", "📥 Lore Ingestion", "⚖️ Truth Auditor", "📊 Graph Nexus"]
    selected_other = st.radio(
        "Choose your path:",
        other_modes,
        label_visibility="collapsed",
        key="other_mode_radio"
    )

    if st.session_state.selected_mode != "⚔️ Play AIRpg":
        st.session_state.selected_mode = selected_other

    mode = st.session_state.selected_mode

    st.divider()

    # Lore Integrity Monitor (Review Queue)
    if is_connected:
        try:
            pending = api_get("/review/pending", params={"limit": 10})
            pending_count = len(pending)
            if pending_count > 0:
                st.markdown("### 🔍 Lore Integrity")
                st.warning(f"⚠️ {pending_count} blocked entities need review")
                if st.button("📋 Open Review Queue"):
                    st.session_state['show_review_queue'] = True
        except Exception:
            pass

    st.divider()

    # Oracle wisdom
    st.markdown("""
    <div class="oracle-quote">
        "In the patterns of contradiction,<br/>
        truth reveals itself to those<br/>
        who dare to look."
    </div>
    """, unsafe_allow_html=True)

    # Version info
    st.caption("v1.0.0 — AIRpg Phase I")

# ==========================================
# MAIN CONTENT
# ==========================================
st.markdown("# ⚗️ The Lore Oracle")
st.caption("*30 years of memory. One source of truth.*")

mode = st.session_state.selected_mode

# ==========================================
# MODE: PLAY AIRPG
# ==========================================
if mode == "⚔️ Play AIRpg":
    st.markdown("## ⚔️ AIRpg — The Grounded Dungeon Master")
    st.markdown("*Step into the fiction. The Oracle becomes your guide.*")

    with st.sidebar:
        st.markdown("---")
        st.subheader("🎲 Game Rules")
        st.markdown("""
**You control:**
- Your character's actions (attempts)
- What you say and ask
- Where you try to go

**The DM controls:**
- What exists in the world
- Outcomes of your actions
- All NPCs and enemies
- Hidden information

*The DM can override agency only with in-world justification (magic, injury, etc.)*
""")

    st.divider()

    if st.session_state.airpg_session_id is None and is_connected:
        st.session_state.airpg_session_id = str(uuid.uuid4())
        intro_msg = (
            "*The Oracle stirs...*\n\n"
            "Before we begin, I need to understand the shape of our story.\n\n"
            "**What kind of world are we in?**\n\n"
            "*Examples: A rain-swept border town, a grimy city district, "
            "a haunted forest, a quiet monastery...*"
        )
        st.session_state.airpg_history.append({"role": "assistant", "content": intro_msg})

    # Display history
    for msg in st.session_state.airpg_history:
        avatar = "🎭" if msg["role"] == "assistant" else "⚔️"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    if is_connected and (player_input := st.chat_input("What do you do?")):
        st.session_state.airpg_history.append({"role": "user", "content": player_input})
        with st.chat_message("user", avatar="⚔️"):
            st.markdown(player_input)

        with st.chat_message("assistant", avatar="🎭"):
            with st.spinner("*The DM considers...*"):
                try:
                    payload = {
                        "session_id": st.session_state.airpg_session_id,
                        "history": st.session_state.airpg_history[:-1],
                        "session_0_complete": st.session_state.airpg_session_0_complete,
                        "session_0_answers": st.session_state.airpg_session_0_answers,
                        "player_input": player_input,
                    }
                    data = api_post("/dm/next", payload, timeout=60)
                    response = data.get("response", "")
                    st.session_state.airpg_session_0_complete = data.get(
                        "session_0_complete",
                        st.session_state.airpg_session_0_complete
                    )
                    st.session_state.airpg_session_0_answers = data.get(
                        "session_0_answers",
                        st.session_state.airpg_session_0_answers
                    )
                    st.markdown(response)
                    st.session_state.airpg_history.append({"role": "assistant", "content": response})
                except Exception as e:
                    st.error(f"DM Error: {e}")

# ==========================================
# MODE: QUERY THE ORACLE
# ==========================================
elif mode == "🔮 Query The Oracle":
    st.markdown("## 🔮 Query The Oracle")
    st.markdown("*Speak your question, and the Oracle shall search the depths of recorded lore...*")
    st.divider()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🧙" if msg["role"] == "assistant" else "⚔️"):
            st.markdown(msg["content"])

    if is_connected and (prompt := st.chat_input("What secrets do you seek from the archives?")):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="⚔️"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🧙"):
            with st.spinner("*The Oracle consults the ancient records...*"):
                try:
                    data = api_post("/oracle/query", {"query": prompt})
                    response_text = data.get("response", "")
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                except Exception as e:
                    st.error(f"An error occurred: {e}")

    if st.session_state.messages:
        st.divider()
        if st.button("🗑️ Clear Communion"):
            st.session_state.messages = []
            st.rerun()

# ==========================================
# MODE: LORE INGESTION
# ==========================================
elif mode == "📥 Lore Ingestion":
    st.markdown("## 📥 Lore Ingestion")
    st.markdown("*Feed the Oracle new knowledge from your campaign files.*")
    st.divider()

    uploaded_files = st.file_uploader(
        "Drop files here",
        type=["txt", "md", "json"],
        accept_multiple_files=True
    )

    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} file(s) selected")

        if st.button("⚗️ BEGIN EXTRACTION", type="primary", disabled=not is_connected):
            st.divider()
            with st.spinner("Uploading and processing..."):
                try:
                    files_payload = []
                    for f in uploaded_files:
                        content = f.getvalue()
                        mime = "text/plain"
                        if f.name.endswith(".json"):
                            mime = "application/json"
                        files_payload.append(
                            ("files", (f.name, content, mime))
                        )

                    url = f"{API_BASE}/upload"
                    resp = requests.post(
                        url,
                        files=files_payload,
                        data={"process_immediately": "true"},
                        timeout=120,
                    )
                    resp.raise_for_status()
                    result = resp.json()

                    st.session_state.ingestion_results = result.get("processing_results", [])
                    totals_nodes = sum(r.get("nodes_created", 0) for r in st.session_state.ingestion_results if r.get("status") == "processed")
                    totals_rels = sum(r.get("relationships_created", 0) for r in st.session_state.ingestion_results if r.get("status") == "processed")
                    st.session_state.ingestion_totals = {"nodes": totals_nodes, "rels": totals_rels}
                    st.session_state.ingestion_errors = [
                        f"{r.get('filename')}: {r.get('error')}"
                        for r in st.session_state.ingestion_results
                        if r.get("status") == "failed"
                    ]
                    st.rerun()
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")

    if st.session_state.ingestion_results:
        st.divider()
        totals = st.session_state.ingestion_totals or {"nodes": 0, "rels": 0}
        st.success(
            f"### ✅ INGESTION COMPLETE\n"
            f"**{totals['nodes']} entities** and **{totals['rels']} relationships** saved."
        )

        if st.session_state.ingestion_errors:
            for err in st.session_state.ingestion_errors:
                st.warning(err)

        if st.button("🗑️ Clear & Upload More"):
            st.session_state.ingestion_results = None
            st.rerun()

# ==========================================
# MODE: TRUTH AUDITOR
# ==========================================
elif mode == "⚖️ Truth Auditor":
    st.markdown("## ⚖️ The Truth Auditor")
    st.markdown("*Submit new lore for verification against the sacred canon.*")
    st.divider()

    submission = st.text_area("📜 New Lore Submission", height=200)

    if st.button("⚖️ SUBMIT FOR AUDIT", type="primary", disabled=not submission or not is_connected):
        with st.spinner("Auditing submission against the graph canon..."):
            try:
                result = api_post("/audit", {"submission": submission}, timeout=60)
                st.session_state.audit_result = result
            except Exception as e:
                st.error(f"An error occurred during the audit: {e}")
                st.session_state.audit_result = None

    if st.session_state.audit_result:
        st.divider()
        res = st.session_state.audit_result
        if res.get("status") == "SAFE":
            st.success("✅ **SAFE**: No contradictions found.")
        else:
            st.error("🚨 **CONTRADICTION DETECTED**")
            st.json(res.get("contradictions"))

        if st.button("🗑️ Clear Audit"):
            st.session_state.audit_result = None
            st.rerun()

# ==========================================
# MODE: GRAPH NEXUS
# ==========================================
elif mode == "📊 Graph Nexus":
    st.markdown("## 📊 The Graph Nexus")
    st.markdown("*Behold the structure of recorded memory.*")
    st.divider()

    if is_connected:
        col1, col2 = st.columns([3, 1])
        with col2:
            limit = st.number_input("Node Limit", 10, 200, 50)
            if st.button("🔄 Refresh"):
                st.rerun()

        with col1:
            try:
                data = api_get("/graph/basic", params={"limit": limit})
            except Exception as e:
                st.error(f"Graph fetch failed: {e}")
                data = []

            if data:
                nodes = []
                edges = []
                seen = set()

                for row in data:
                    source = row["source"]
                    target = row["target"]
                    if source not in seen:
                        nodes.append(Node(id=source, label=source, size=20, color="#ff6b6b"))
                        seen.add(source)
                    if target not in seen:
                        nodes.append(Node(id=target, label=target, size=20, color="#00ccff"))
                        seen.add(target)
                    edges.append(Edge(source=source, target=target, label=row["type"]))

                config = Config(width="100%", height=600, directed=True, physics=True)
                agraph(nodes=nodes, edges=edges, config=config)
            else:
                st.info("No data to visualize.")

# ==========================================
# REVIEW QUEUE MODAL
# ==========================================
if st.session_state.get('show_review_queue') and is_connected:
    st.markdown("---")
    st.markdown("## 📋 Lore Review Queue")
    st.markdown("*Entities blocked due to contradictions with existing canon.*")

    try:
        pending_reviews = api_get("/review/pending", params={"limit": 10})
    except Exception as e:
        st.error(f"Failed to fetch review queue: {e}")
        pending_reviews = []

    if pending_reviews:
        for review in pending_reviews:
            with st.container():
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.markdown(f"### {review['entity_name']} ({review['entity_type']})")
                    st.caption(f"**Conflict:** {review['contradiction']}")
                    st.caption(f"Severity: `{review['severity']}` | Session: `{review['session_id'][:8]}...`")

                with col2:
                    if st.button("✅ Approve", key=f"approve_{review['id']}"):
                        try:
                            api_post(f"/review/{review['id']}/approve", {})
                            st.success(f"Approved: {review['entity_name']}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Approve failed: {e}")

                    if st.button("❌ Reject", key=f"reject_{review['id']}"):
                        try:
                            api_post(f"/review/{review['id']}/reject", {})
                            st.info(f"Rejected: {review['entity_name']}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Reject failed: {e}")

                st.markdown("---")
    else:
        st.success("✨ No pending reviews. All clear!")

    if st.button("Close Review Queue"):
        st.session_state['show_review_queue'] = False
        st.rerun()

# ==========================================
# FOOTER
# ==========================================
st.divider()
st.markdown("""
<div style="text-align: center; color: var(--text-muted); font-size: 0.8rem; font-family: 'Crimson Text', serif; font-style: italic;">
    The Lore Oracle — Guardian of Canon
</div>
""", unsafe_allow_html=True)
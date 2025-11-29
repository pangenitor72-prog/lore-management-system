import streamlit as st
import os
import sys
import asyncio
from dotenv import load_dotenv
from neo4j import GraphDatabase, AsyncGraphDatabase  # Use sync driver for Streamlit
from streamlit_agraph import agraph, Node, Edge, Config

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.ingestor import LoreIngestor
from src.auditor_agent import AuditorAgent
from src.query_agent import QueryAgent
from src.neo4j_adapter import Neo4jDatabase

# Load Environment
load_dotenv()

# Config from environment
DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
DB_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
GEMINI_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

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

# Initialize Session State
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

# Database Connection (Cached) - Using SYNC driver for Streamlit
@st.cache_resource
def get_sync_driver():
    """Create a synchronous Neo4j driver for Streamlit compatibility."""
    driver = GraphDatabase.driver(DB_URI, auth=(DB_USER, DB_PASSWORD))
    # Verify connectivity
    driver.verify_connectivity()
    return driver

def run_query(driver, query, params=None):
    """Run a Cypher query synchronously."""
    if params is None:
        params = {}
    with driver.session() as session:
        result = session.run(query, params)
        return [record.data() for record in result]

# Initialize connections
try:
    neo4j_driver = get_sync_driver()
    is_connected = True
    connection_error = None
except Exception as e:
    is_connected = False
    connection_error = str(e)
    neo4j_driver = None

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
        st.error(f"Connection failed: {connection_error}")
    
    st.divider()
    
    # Mode Selection
    st.markdown("### 📜 Consult The Archives")
    mode = st.radio(
        "Choose your path:",
        ["⚔️ Play AIRpg", "🔮 Query The Oracle", "📥 Lore Ingestion", "⚖️ Truth Auditor", "📊 Graph Nexus"],
        label_visibility="collapsed"
    )
    
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

# ==========================================
# MODE: PLAY AIRPG
# ==========================================
if mode == "⚔️ Play AIRpg":
    st.markdown("## ⚔️ AIRpg — The Grounded Dungeon Master")
    st.markdown("*Step into the fiction. The Oracle becomes your guide.*")
    
    st.divider()
    
    # Initialize AIRpg session state
    if "airpg_session_id" not in st.session_state:
        st.session_state.airpg_session_id = None
    if "airpg_history" not in st.session_state:
        st.session_state.airpg_history = []
    if "airpg_session_0_complete" not in st.session_state:
        st.session_state.airpg_session_0_complete = False
    if "airpg_session_0_answers" not in st.session_state:
        st.session_state.airpg_session_0_answers = {}
    
    # Session Controls
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 New Session", type="secondary"):
            st.session_state.airpg_session_id = None
            st.session_state.airpg_history = []
            st.session_state.airpg_session_0_complete = False
            st.session_state.airpg_session_0_answers = {}
            st.rerun()
    
    # Start new session if needed
    if st.session_state.airpg_session_id is None and is_connected:
        # Create new session
        import uuid
        st.session_state.airpg_session_id = str(uuid.uuid4())
        
        # Show Session 0 intro
        intro_msg = (
            "*The Oracle stirs...*\n\n"
            "Before we begin, I need to understand the shape of our story.\n\n"
            "**What kind of world are we in?**\n\n"
            "*Examples: A rain-swept border town, a grimy city district, "
            "a haunted forest, a quiet monastery...*"
        )
        st.session_state.airpg_history.append({"role": "assistant", "content": intro_msg})
    
    # Display conversation history
    for msg in st.session_state.airpg_history:
        avatar = "🎭" if msg["role"] == "assistant" else "⚔️"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
    
    # Chat input
    if is_connected and (player_input := st.chat_input("What do you do?")):
        # Add player message
        st.session_state.airpg_history.append({"role": "user", "content": player_input})
        with st.chat_message("user", avatar="⚔️"):
            st.markdown(player_input)
        
        # Generate DM response
        with st.chat_message("assistant", avatar="🎭"):
            with st.spinner("*The DM considers...*"):
                try:
                    # Import and run DM Agent
                    from src.dm_agent import DMAgent
                    
                    async def get_dm_response():
                        async_driver = AsyncGraphDatabase.driver(DB_URI, auth=(DB_USER, DB_PASSWORD))
                        db = Neo4jDatabase(DB_URI, (DB_USER, DB_PASSWORD))
                        await db.connect()
                        
                        try:
                            dm = DMAgent(db, GEMINI_KEY)
                            await dm.start_session(st.session_state.airpg_session_id)
                            
                            # Restore session state
                            dm.session_0_complete = st.session_state.airpg_session_0_complete
                            dm.session_0_answers = st.session_state.airpg_session_0_answers.copy()
                            dm.history = [h.copy() for h in st.session_state.airpg_history[:-1]]  # Exclude current input
                            
                            # Process input
                            response = await dm.process_input(player_input)
                            
                            # Save session state back
                            st.session_state.airpg_session_0_complete = dm.session_0_complete
                            st.session_state.airpg_session_0_answers = dm.session_0_answers.copy()
                            
                            return response
                        finally:
                            await db.close()
                    
                    response = asyncio.run(get_dm_response())
                    st.markdown(response)
                    st.session_state.airpg_history.append({"role": "assistant", "content": response})
                    
                except Exception as e:
                    st.error(f"DM Error: {e}")
                    import traceback
                    st.code(traceback.format_exc())

# ==========================================
# MODE: QUERY THE ORACLE
# ==========================================
elif mode == "🔮 Query The Oracle":
    st.markdown("## 🔮 Query The Oracle")
    st.markdown("*Speak your question, and the Oracle shall search the depths of recorded lore...*")
    
    st.divider()
    
    # Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🧙" if msg["role"] == "assistant" else "⚔️"):
            st.markdown(msg["content"])
    
    # Chat Input
    if is_connected and (prompt := st.chat_input("What secrets do you seek from the archives?")):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="⚔️"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant", avatar="🧙"):
            with st.spinner("*The Oracle consults the ancient records...*"):
                try:
                    # Use Query Agent (async method wrapped for Streamlit)
                    # For now, we'll use a direct invocation since QueryAgent is designed for async.
                    # To keep it simple in Streamlit (sync), we can re-use the logic or adapt QueryAgent.
                    # Since QueryAgent is async, we'll run it in a loop if possible, or fallback to the synchronous implementation for now to avoid event loop issues.
                    
                    # FALLBACK: Synchronous implementation (similar to before, but using the class if we had a sync wrapper)
                    # Ideally, QueryAgent should have a sync_query method.
                    # For this step, I'll keep the working logic inline but updated to be cleaner.
                    
                    # ... (Keeping existing inline logic for stability until async wrapper is ready) ...
                    
                    # 1. Extraction (re-using inline for now)
                    import google.generativeai as genai
                    genai.configure(api_key=GEMINI_KEY)
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    
                    extraction_prompt = f"""Extract named entities from this D&D question.
Return ONLY a JSON array of entity names to search for.
Examples: ["Vulture Clan", "Kael", "Shadow Realm"]
If no specific entities, return [""].
Question: "{prompt}"
JSON array:"""
                    
                    extraction_response = model.generate_content(
                        extraction_prompt,
                        generation_config={"temperature": 0.1, "max_output_tokens": 200}
                    )
                    
                    # Parse
                    try:
                        extracted_text = extraction_response.text.strip()
                        extracted_text = re.sub(r'^```json\s*', '', extracted_text)
                        extracted_text = re.sub(r'^```\s*', '', extracted_text)
                        extracted_text = re.sub(r'\s*```$', '', extracted_text)
                        search_entities = json.loads(extracted_text)
                    except:
                        search_entities = []

                    # 2. Retrieval
                    all_context = []
                    seen_names = set()
                    
                    # 2a. Entity Search
                    for entity in search_entities:
                        if entity and len(entity) > 1:
                            entity_query = """
                            MATCH (n)
                            WHERE toLower(n.name) CONTAINS toLower($term)
                            OPTIONAL MATCH (n)-[r]-(related)
                            RETURN n.name AS name, labels(n)[0] AS type,
                                   n.description AS description,
                                   collect(DISTINCT {rel: type(r), target: related.name, targetType: labels(related)[0]})[0..8] AS relationships
                            LIMIT 5
                            """
                            results = run_query(neo4j_driver, entity_query, {"term": entity})
                            for r in results:
                                if r['name'] and r['name'] not in seen_names:
                                    seen_names.add(r['name'])
                                    all_context.append(r)
                                    
                    # 2b. Keyword Search fallback
                    if len(all_context) < 3:
                        keywords = [w for w in prompt.lower().split() if len(w) > 3]
                        for keyword in keywords[:3]:
                            keyword_query = """
                            MATCH (n)
                            WHERE toLower(n.description) CONTAINS toLower($term)
                            OPTIONAL MATCH (n)-[r]-(related)
                            RETURN n.name AS name, labels(n)[0] AS type,
                                   n.description AS description,
                                   collect(DISTINCT {rel: type(r), target: related.name, targetType: labels(related)[0]})[0..5] AS relationships
                            LIMIT 3
                            """
                            results = run_query(neo4j_driver, keyword_query, {"term": keyword})
                            for r in results:
                                if r['name'] and r['name'] not in seen_names:
                                    seen_names.add(r['name'])
                                    all_context.append(r)

                    # 3. Format Context
                    if all_context:
                        context = "=== LORE CONTEXT ===\n"
                        for entity in all_context:
                            context += f"### {entity['name']} ({entity['type']})\n{entity.get('description', '')}\n"
                            if entity.get('relationships'):
                                context += "**Connections:**\n"
                                for rel in entity['relationships'][:6]:
                                    context += f"- {rel.get('rel')} -> {rel.get('target')}\n"
                            context += "\n"
                    else:
                        context = "No direct lore found."

                    # 4. Generate Answer
                    oracle_prompt = f"""{context}
=== QUESTION ===
{prompt}

Answer as the Lore Oracle (wise, archaic but clear). Use the context provided."""
                    
                    response = model.generate_content(oracle_prompt)
                    
                    # Show context
                    if all_context:
                        with st.expander(f"📚 Context used ({len(all_context)} entities)", expanded=False):
                            for e in all_context:
                                st.markdown(f"• **{e['name']}**")

                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    
                except Exception as e:
                    st.error(f"Query failed: {e}")

    # Clear chat
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
    
    # Initialize Ingestor
    # ingestor = LoreIngestor(neo4j_driver, GEMINI_KEY) # OLD SYNC WAY
    
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
            progress_bar = st.progress(0, text="Starting...")
            
            all_results = []
            total_nodes = 0
            total_rels = 0
            errors = []
            
            for idx, file in enumerate(uploaded_files):
                filename = file.name
                progress_bar.progress((idx) / len(uploaded_files), text=f"Processing {filename}...")
                
                content = file.getvalue().decode("utf-8")
                
                try:
                    # 1. Process (Extract) - Async wrapper
                    async def run_ingestion():
                         async_driver = AsyncGraphDatabase.driver(DB_URI, auth=(DB_USER, DB_PASSWORD))
                         local_ingestor = LoreIngestor(async_driver, GEMINI_KEY)
                         try:
                             # Process
                             r_data = await local_ingestor.process_file_content(filename, content)
                             # Save
                             s_stats = await local_ingestor.save_to_neo4j(r_data["data"], filename)
                             return r_data, s_stats
                         finally:
                             await async_driver.close()

                    result_data, save_stats = asyncio.run(run_ingestion())
                    
                    total_nodes += save_stats["nodes_saved"]
                    total_rels += save_stats["rels_saved"]
                    
                    all_results.append({
                        "filename": filename,
                        "stats": save_stats,
                        "data": result_data["data"],
                        "status": "success"
                    })
                    
                except Exception as e:
                    errors.append(f"{filename}: {e}")
            
            progress_bar.progress(1.0, text="Complete!")
            
            st.session_state.ingestion_results = all_results
            st.session_state.ingestion_totals = {"nodes": total_nodes, "rels": total_rels}
            st.session_state.ingestion_errors = errors
            st.rerun()

    # Display Results
    if st.session_state.ingestion_results:
        st.divider()
        totals = st.session_state.ingestion_totals
        st.success(f"### ✅ INGESTION COMPLETE\n**{totals['nodes']} entities** and **{totals['rels']} relationships** saved.")
        
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
    
    # Initialize Auditor (using async bridge if needed, but for now direct Gemini call via Auditor logic logic re-implementation for sync)
    # We will use the AuditorAgent class structure but adapt it for sync Streamlit execution
    
    submission = st.text_area("📜 New Lore Submission", height=200)
    
    if st.button("⚖️ SUBMIT FOR AUDIT", type="primary", disabled=not submission):
        with st.spinner("Auditing..."):
            # Using Auditor Logic directly here for Sync compatibility
            # (AuditorAgent is async, so we manually implement the flow using AuditorAgent helper methods if they were static, 
            # or just replicate the flow here for stability)
            
            # 1. AuditorAgent Logic Replication (Sync)
            auditor = AuditorAgent(Neo4jDatabase(DB_URI, (DB_USER, DB_PASSWORD)), GEMINI_KEY)
            
            # We need an async loop to run the AuditorAgent methods properly
            # Or we fallback to the manual implementation we had before which worked reliably.
            # Given user wants stability, let's stick to the manual implementation for now but cleaner.
            
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            # 1. Extract Entities from submission
            extract_prompt = f"Extract entity names from this text as a JSON list. Text: {submission}"
            resp = model.generate_content(extract_prompt)
            try:
                entities = json.loads(re.search(r'\[.*\]', resp.text, re.DOTALL).group())
            except:
                entities = []
            
            # 2. Fetch Graph Truth
            truth_context = ""
            if entities:
                q = "MATCH (n) WHERE n.name IN $names RETURN n.name, n.description, labels(n)[0] as type"
                res = run_query(neo4j_driver, q, {"names": entities})
                for r in res:
                    truth_context += f"- {r['name']} ({r['type']}): {r['description']}\n"
            
            # 3. Audit
            audit_prompt = f"""EXISTING TRUTH:\n{truth_context}\n\nNEW SUBMISSION:\n{submission}\n\nCheck for contradictions. Return JSON with status (SAFE/CONTRADICTION) and contradictions list."""
            
            final_resp = model.generate_content(audit_prompt)
            try:
                # Naive parse
                json_str = re.search(r'\{.*\}', final_resp.text, re.DOTALL).group()
                result = json.loads(json_str)
            except:
                result = {"status": "SAFE", "notes": final_resp.text}
            
            st.session_state.audit_result = result
            
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
            query = f"""
            MATCH (n)-[r]->(m)
            RETURN n.name AS source, labels(n)[0] AS source_label, 
                   m.name AS target, labels(m)[0] AS target_label, 
                   type(r) AS type
            LIMIT {limit}
            """
            data = run_query(neo4j_driver, query)
            
            if data:
                nodes = []
                edges = []
                seen = set()
                
                for row in data:
                    if row['source'] not in seen:
                        nodes.append(Node(id=row['source'], label=row['source'], size=20, color="#ff6b6b"))
                        seen.add(row['source'])
                    if row['target'] not in seen:
                        nodes.append(Node(id=row['target'], label=row['target'], size=20, color="#00ccff"))
                        seen.add(row['target'])
                    edges.append(Edge(source=row['source'], target=row['target'], label=row['type']))
                
                config = Config(width="100%", height=600, directed=True, physics=True)
                agraph(nodes=nodes, edges=edges, config=config)
            else:
                st.info("No data to visualize.")

# ==========================================
# FOOTER
# ==========================================
st.divider()
st.markdown("""
<div style="text-align: center; color: var(--text-muted); font-size: 0.8rem; font-family: 'Crimson Text', serif; font-style: italic;">
    The Lore Oracle — Guardian of Canon
</div>
""", unsafe_allow_html=True)

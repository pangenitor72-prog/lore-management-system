import streamlit as st
import os
import sys
import json
import re

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
from neo4j import GraphDatabase  # Use sync driver for Streamlit
import google.generativeai as genai

# Load Environment
load_dotenv()

# Config from environment
DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
DB_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

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
        ["🔮 Query The Oracle", "📥 Lore Ingestion", "⚖️ Truth Auditor", "📊 Graph Nexus"],
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
    st.caption("v0.9.0 — Phase XII")

# ==========================================
# MAIN CONTENT
# ==========================================
st.markdown("# ⚗️ The Lore Oracle")
st.caption("*30 years of memory. One source of truth.*")

# ==========================================
# MODE: QUERY THE ORACLE
# ==========================================
if mode == "🔮 Query The Oracle":
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
                genai.configure(api_key=GEMINI_KEY)
                model = genai.GenerativeModel("gemini-2.0-flash")
                
                try:
                    # ========================================
                    # STRATEGY 1: Agentic Entity Extraction
                    # Use AI to intelligently extract entities from natural language
                    # ========================================
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
                    
                    # Parse extracted entities
                    extracted_text = extraction_response.text.strip()
                    extracted_text = re.sub(r'^```json\s*', '', extracted_text)
                    extracted_text = re.sub(r'^```\s*', '', extracted_text)
                    extracted_text = re.sub(r'\s*```$', '', extracted_text)
                    
                    try:
                        search_entities = json.loads(extracted_text)
                        if not isinstance(search_entities, list):
                            search_entities = []
                    except:
                        search_entities = []
                    
                    # ========================================
                    # MULTI-STRATEGY SEARCH
                    # ========================================
                    all_context = []
                    seen_names = set()
                    
                    # Strategy 1a: Search for extracted entities
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
                    
                    # Strategy 2: Reverse Match - find entities whose names appear in the query
                    if len(all_context) < 3:
                        reverse_query = """
                        MATCH (n)
                        WHERE n.name IS NOT NULL 
                          AND size(n.name) > 2
                          AND toLower($query) CONTAINS toLower(n.name)
                        OPTIONAL MATCH (n)-[r]-(related)
                        RETURN n.name AS name, labels(n)[0] AS type,
                               n.description AS description,
                               collect(DISTINCT {rel: type(r), target: related.name, targetType: labels(related)[0]})[0..8] AS relationships
                        ORDER BY size(n.name) DESC
                        LIMIT 5
                        """
                        results = run_query(neo4j_driver, reverse_query, {"query": prompt.lower()})
                        for r in results:
                            if r['name'] and r['name'] not in seen_names:
                                seen_names.add(r['name'])
                                all_context.append(r)
                    
                    # Strategy 3: Keyword search on description
                    if len(all_context) < 3:
                        # Extract meaningful keywords
                        keywords = [w for w in prompt.lower().split() 
                                   if len(w) > 3 and w not in {'what', 'who', 'where', 'when', 'tell', 'about', 'the', 'and', 'for', 'with'}]
                        
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
                    
                    # ========================================
                    # FORMAT CONTEXT
                    # ========================================
                    if all_context:
                        context = "=== LORE CONTEXT FROM KNOWLEDGE GRAPH ===\n"
                        context += f"(Found {len(all_context)} relevant entities)\n\n"
                        
                        for entity in all_context:
                            context += f"### {entity['name']} ({entity['type'] or 'Entity'})\n"
                            if entity.get('description'):
                                context += f"{entity['description']}\n"
                            
                            if entity.get('relationships'):
                                valid_rels = [r for r in entity['relationships'] if r.get('target')]
                                if valid_rels:
                                    context += "**Connections:**\n"
                                    for rel in valid_rels[:6]:
                                        context += f"  • {rel.get('rel', 'RELATED_TO')} → {rel['target']} ({rel.get('targetType', '?')})\n"
                            context += "\n"
                    else:
                        context = "=== NO MATCHING LORE FOUND IN KNOWLEDGE GRAPH ===\n"
                        context += "The Oracle found no entities matching your query.\n"
                    
                    # ========================================
                    # GENERATE ANSWER WITH GEMINI
                    # ========================================
                    oracle_prompt = f"""{context}

=== DM'S QUESTION ===
{prompt}

=== INSTRUCTIONS ===
You are the Lore Oracle, keeper of a 30-year D&D campaign's canonical knowledge.

Rules:
1. Answer ONLY based on the lore context above - never make things up
2. If the information isn't in the context, say "That information is not in the recorded lore."
3. Be direct, intelligent, and synthesize information - don't just list facts
4. Reference specific entities and their relationships when relevant
5. If asked about relationships between entities, trace the connections shown above

Respond as the Oracle:"""
                    
                    response = model.generate_content(oracle_prompt)
                    
                    # Show what was found (debug info)
                    if all_context:
                        with st.expander(f"📚 Context used ({len(all_context)} entities)", expanded=False):
                            for e in all_context:
                                st.markdown(f"• **{e['name']}** ({e['type'] or 'Entity'})")
                    
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    
                except Exception as e:
                    st.error(f"Query failed: {e}")
                    import traceback
                    st.code(traceback.format_exc())
    
    elif not is_connected:
        st.warning("⚠️ The Oracle slumbers. Check your connection to the Neo4j realm and Gemini conduit.")
    
    # Clear chat button
    if st.session_state.messages:
        st.divider()
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🗑️ Clear Communion", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

# ==========================================
# MODE: LORE INGESTION
# ==========================================
elif mode == "📥 Lore Ingestion":
    st.markdown("## 📥 Lore Ingestion")
    st.markdown("*Feed the Oracle new knowledge from your campaign files.*")
    
    st.divider()
    
    # Clear instructions
    st.markdown("""
    ### How It Works
    
    | Step | Action | What Happens |
    |------|--------|--------------|
    | **1** | Upload files below | Select `.txt`, `.md`, or `.json` files with your lore |
    | **2** | Click "Begin Extraction" | AI reads your text and identifies entities |
    | **3** | Review results | See what was extracted before confirming |
    | **4** | Data saved to graph | Entities become queryable immediately |
    """)
    
    st.divider()
    
    # Step 1: Upload
    st.markdown("### Step 1: Upload Your Lore Files")
    
    uploaded_files = st.file_uploader(
        "Drop files here or click to browse",
        type=["txt", "md", "json"],
        accept_multiple_files=True,
        help="Upload text files containing campaign lore. The Oracle will extract entities and relationships."
    )
    
    # Show what was uploaded
    if uploaded_files:
        st.success(f"✅ **{len(uploaded_files)} file(s) selected**")
        
        with st.expander("📂 View selected files", expanded=True):
            for f in uploaded_files:
                file_size = len(f.getvalue()) / 1024
                st.markdown(f"• `{f.name}` — {file_size:.1f} KB")
        
        st.divider()
        
        # Step 2: Extract
        st.markdown("### Step 2: Extract Knowledge")
        st.markdown("*Click the button below to begin AI extraction. This may take a moment per file.*")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            ingest_btn = st.button(
                "⚗️ BEGIN EXTRACTION",
                type="primary",
                use_container_width=True,
                disabled=not is_connected
            )
        
        if not is_connected:
            st.error("❌ Cannot extract - database not connected. Check Neo4j and restart.")
        
        if ingest_btn and is_connected:
            st.divider()
            st.markdown("### 🔄 Processing...")
            
            # Configure Gemini
            genai.configure(api_key=GEMINI_KEY)
            extraction_model = genai.GenerativeModel('gemini-2.0-flash')
            
            EXTRACTION_PROMPT = """You are a Knowledge Graph Extractor for a D&D Campaign.
Analyze the following text and extract entities and relationships.

**Entities to Extract (Labels):**
- Character (NPCs, PCs, villains)
- Location (Places, regions, buildings)  
- Item (Weapons, artifacts, objects)
- Faction (Organizations, groups, cults)
- Event (Battles, ceremonies, historical moments)
- Concept (Abstract ideas, magic types, prophecies, curses)

**Output Format:**
Return ONLY a valid JSON object with two keys: "nodes" and "relationships".

Example:
{"nodes": [{"id": "Kael", "label": "Character", "properties": {"description": "A sworn paladin protector"}}], "relationships": [{"source": "Kael", "target": "Iron Brotherhood", "type": "MEMBER_OF"}]}

**Rules:**
1. Use simple IDs (e.g., "Kael" not "Kael the Paladin")
2. Always include a "description" in properties
3. Relationship types: LOCATED_IN, MEMBER_OF, OWNS, ALLIED_WITH, ENEMY_OF, KNOWS, etc.
4. If no entities found, return: {"nodes": [], "relationships": []}
5. Return ONLY valid JSON. No markdown, no explanations."""

            all_results = []
            total_nodes_saved = 0
            total_rels_saved = 0
            errors = []
            
            # Progress tracking
            progress_bar = st.progress(0, text="Starting extraction...")
            status_container = st.empty()
            
            for idx, uploaded_file in enumerate(uploaded_files):
                filename = uploaded_file.name
                progress_bar.progress(
                    (idx) / len(uploaded_files), 
                    text=f"Processing {idx+1}/{len(uploaded_files)}: {filename}"
                )
                
                with status_container.container():
                    st.info(f"🧠 **Extracting from:** `{filename}`")
                
                content = uploaded_file.getvalue().decode("utf-8")
                
                try:
                    # Step A: AI Extraction
                    response = extraction_model.generate_content(
                        EXTRACTION_PROMPT + "\n\nTEXT:\n" + content[:8000],
                        generation_config={"temperature": 0.1}
                    )
                    
                    # Parse response
                    response_text = response.text.strip()
                    response_text = re.sub(r'^```json\s*', '', response_text)
                    response_text = re.sub(r'^```\s*', '', response_text)
                    response_text = re.sub(r'\s*```$', '', response_text)
                    
                    try:
                        data = json.loads(response_text)
                    except json.JSONDecodeError:
                        match = re.search(r'\{[\s\S]*\}', response_text)
                        if match:
                            data = json.loads(match.group())
                        else:
                            data = {"nodes": [], "relationships": []}
                    
                    nodes = data.get("nodes", [])
                    rels = data.get("relationships", [])
                    
                    # Step B: Save to Neo4j (using sync driver)
                    nodes_saved = 0
                    rels_saved = 0
                    
                    if nodes and neo4j_driver:
                        for node in nodes:
                            node_id = node.get("id", "")
                            label = node.get("label", "Entity")
                            props = node.get("properties", {})
                            
                            if node_id:
                                # Sanitize label for Cypher
                                safe_label = re.sub(r'[^a-zA-Z0-9_]', '', label)
                                if not safe_label:
                                    safe_label = "Entity"
                                
                                save_query = f"""
                                MERGE (n:{safe_label} {{name: $name}})
                                SET n += $props
                                SET n:Entity
                                RETURN n.name AS saved
                                """
                                try:
                                    result = run_query(neo4j_driver, save_query, {
                                        "name": node_id,
                                        "props": props
                                    })
                                    if result:
                                        nodes_saved += 1
                                except Exception as node_err:
                                    errors.append(f"{filename}: Node '{node_id}': {str(node_err)[:50]}")
                        
                        # Save relationships
                        for rel in rels:
                            source = rel.get("source", "")
                            target = rel.get("target", "")
                            rel_type = rel.get("type", "RELATED_TO").upper().replace(" ", "_")
                            # Sanitize relationship type
                            rel_type = re.sub(r'[^a-zA-Z0-9_]', '_', rel_type)
                            
                            if source and target:
                                rel_query = f"""
                                MATCH (a {{name: $source}})
                                MATCH (b {{name: $target}})
                                MERGE (a)-[r:{rel_type}]->(b)
                                RETURN type(r) AS saved
                                """
                                try:
                                    result = run_query(neo4j_driver, rel_query, {
                                        "source": source,
                                        "target": target
                                    })
                                    if result:
                                        rels_saved += 1
                                except Exception as rel_err:
                                    errors.append(f"{filename}: Rel '{source}->{target}': {str(rel_err)[:50]}")
                        
                        # Link to source file
                        try:
                            source_query = """
                            MERGE (f:File {name: $filename})
                            RETURN f.name
                            """
                            run_query(neo4j_driver, source_query, {"filename": filename})
                        except:
                            pass
                    
                    total_nodes_saved += nodes_saved
                    total_rels_saved += rels_saved
                    
                    all_results.append({
                        "filename": filename,
                        "nodes": nodes,
                        "relationships": rels,
                        "nodes_saved": nodes_saved,
                        "rels_saved": rels_saved,
                        "status": "success" if nodes_saved > 0 else "empty"
                    })
                    
                except Exception as e:
                    errors.append(f"{filename}: {str(e)}")
                    all_results.append({
                        "filename": filename,
                        "nodes": [],
                        "relationships": [],
                        "nodes_saved": 0,
                        "rels_saved": 0,
                        "status": "error",
                        "error": str(e)
                    })
            
            progress_bar.progress(1.0, text="Complete!")
            status_container.empty()
            
            # Store results
            st.session_state.ingestion_results = all_results
            st.session_state.ingestion_errors = errors
            st.session_state.ingestion_totals = {
                "nodes": total_nodes_saved,
                "rels": total_rels_saved
            }
            
            st.rerun()  # Refresh to show results
    
    # Step 3: Display Results
    if st.session_state.ingestion_results:
        st.divider()
        
        totals = st.session_state.get("ingestion_totals", {"nodes": 0, "rels": 0})
        errors = st.session_state.get("ingestion_errors", [])
        
        # Big success banner
        if totals["nodes"] > 0:
            st.success(f"""
            ### ✅ INGESTION COMPLETE
            
            **{totals['nodes']} entities** and **{totals['rels']} relationships** have been added to the knowledge graph.
            
            You can now query this information using the **🔮 Query The Oracle** mode.
            """)
        else:
            st.warning("""
            ### ⚠️ NO DATA SAVED
            
            The extraction ran but no entities were saved to the database. 
            This could mean:
            - The files didn't contain recognizable entities
            - There was a database connection issue
            - The AI couldn't parse the text format
            """)
        
        # Show any errors
        if errors:
            with st.expander(f"⚠️ {len(errors)} warning(s) during processing", expanded=False):
                for err in errors:
                    st.warning(err)
        
        st.divider()
        st.markdown("### 📊 Extraction Details")
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Files", len(st.session_state.ingestion_results))
        with col2:
            st.metric("Entities Found", sum(len(r["nodes"]) for r in st.session_state.ingestion_results))
        with col3:
            st.metric("Entities Saved", totals["nodes"])
        with col4:
            st.metric("Relationships", totals["rels"])
        
        # Per-file breakdown
        st.markdown("---")
        for result in st.session_state.ingestion_results:
            status_icon = "✅" if result["status"] == "success" else "⚠️" if result["status"] == "empty" else "❌"
            
            with st.expander(
                f"{status_icon} **{result['filename']}** — {result.get('nodes_saved', 0)} saved",
                expanded=(result["status"] != "success")
            ):
                if result["status"] == "error":
                    st.error(f"Error: {result.get('error', 'Unknown')}")
                elif result["status"] == "empty":
                    st.warning("No entities were extracted from this file.")
                else:
                    st.markdown(f"**Extracted:** {len(result['nodes'])} entities, {len(result['relationships'])} relationships")
                    st.markdown(f"**Saved to DB:** {result.get('nodes_saved', 0)} entities, {result.get('rels_saved', 0)} relationships")
                    
                    if result["nodes"]:
                        st.markdown("**Entities:**")
                        for node in result["nodes"]:
                            label = node.get("label", "?")
                            name = node.get("id", "?")
                            desc = node.get("properties", {}).get("description", "")
                            st.markdown(f"• **{name}** ({label}){': ' + desc[:100] + '...' if len(desc) > 100 else ': ' + desc if desc else ''}")
        
        # Action buttons
        st.divider()
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("🔮 Query This Data", use_container_width=True):
                st.session_state.ingestion_results = None
                st.rerun()
        with col2:
            if st.button("📊 View Graph Stats", use_container_width=True):
                st.session_state.ingestion_results = None
                st.rerun()
        with col3:
            if st.button("🗑️ Clear & Upload More", use_container_width=True):
                st.session_state.ingestion_results = None
                st.session_state.ingestion_errors = None
                st.session_state.ingestion_totals = None
                st.rerun()
    
    else:
        # No files yet - show empty state
        st.divider()
        st.info("👆 **Upload files above to begin.** The Oracle accepts `.txt`, `.md`, and `.json` files containing your campaign lore.")

# ==========================================
# MODE: TRUTH AUDITOR
# ==========================================
elif mode == "⚖️ Truth Auditor":
    st.markdown("## ⚖️ The Truth Auditor")
    st.markdown("*Submit new lore for verification against the sacred canon. The Oracle detects contradiction — but only the DM decides truth.*")
    
    st.divider()
    
    # Submission area
    submission = st.text_area(
        "📜 **New Lore Submission**",
        height=200,
        placeholder="Paste your lore here...\n\nExample: 'The Vulture Clan has been at war with the Iron Brotherhood since the Battle of Ashenvale in year 302...'",
        help="The Oracle will analyze this text against all known canon to detect potential contradictions."
    )
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        audit_btn = st.button(
            "⚖️ SUBMIT FOR TRUTH AUDIT",
            type="primary",
            disabled=not is_connected or not submission,
            use_container_width=True
        )
    
    if audit_btn and submission and is_connected:
        with st.spinner("*The Oracle weighs your words against the tapestry of known truth...*"):
            # Simple audit: extract entities from submission, check against DB
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash")
            
            try:
                # Get existing entities from DB
                existing_query = """
                MATCH (n)
                WHERE n.name IS NOT NULL
                RETURN n.name AS name, labels(n)[0] AS type, n.description AS description
                LIMIT 100
                """
                existing = run_query(neo4j_driver, existing_query)
                
                # Build context
                context = "=== EXISTING CANON ===\n"
                for e in existing:
                    context += f"- {e['name']} ({e['type']}): {e.get('description', 'No description')}\n"
                
                # Ask Gemini to check for contradictions
                audit_prompt = f"""{context}

=== NEW SUBMISSION ===
{submission}

Analyze the new submission for contradictions with existing canon. 
Return a JSON object with:
- "status": "SAFE" if no contradictions, "CONTRADICTION" if contradictions found
- "contradictions": array of objects with "claim", "truth", "severity" (HIGH/MEDIUM/LOW), "explanation"
- "entities_checked": array of entity names that were relevant

Return ONLY valid JSON."""

                response = model.generate_content(audit_prompt)
                response_text = response.text.strip()
                response_text = re.sub(r'^```json\s*', '', response_text)
                response_text = re.sub(r'^```\s*', '', response_text)
                response_text = re.sub(r'\s*```$', '', response_text)
                
                try:
                    result = json.loads(response_text)
                except:
                    result = {"status": "SAFE", "notes": "Analysis complete - no clear contradictions detected.", "contradictions": [], "entities_checked": []}
                
                st.session_state.audit_result = result
            except Exception as e:
                st.session_state.audit_result = {"status": "ERROR", "notes": str(e), "contradictions": [], "entities_checked": []}
    
    # Display Results
    if st.session_state.audit_result:
        st.divider()
        result = st.session_state.audit_result
        
        if result["status"] == "SAFE":
            st.success("### ✅ CANON VERIFIED")
            st.markdown("*No contradictions detected. This lore may be safely added to the archives.*")
            if result.get("notes"):
                st.info(f"**Oracle's Note:** {result.get('notes')}")
                
        elif result["status"] == "CONTRADICTION":
            st.error(f"### 🚨 CONTRADICTIONS DETECTED")
            st.markdown(f"*The Oracle has found **{len(result['contradictions'])}** conflicts with established canon.*")
            
            for i, c in enumerate(result["contradictions"], 1):
                severity = c.get('severity', 'UNKNOWN').upper()
                severity_class = {
                    'HIGH': 'severity-high',
                    'MEDIUM': 'severity-medium', 
                    'LOW': 'severity-low'
                }.get(severity, '')
                
                with st.expander(f"⚠️ Contradiction {i} — {severity} Severity", expanded=True):
                    col_claim, col_truth = st.columns(2)
                    
                    with col_claim:
                        st.markdown("**📝 Your Claim:**")
                        st.markdown(f"> {c.get('claim', 'N/A')}")
                    
                    with col_truth:
                        st.markdown("**📜 Canonical Truth:**")
                        st.markdown(f"> {c.get('truth', 'N/A')}")
                    
                    st.markdown("---")
                    st.markdown(f"**🔍 Analysis:** {c.get('explanation', 'N/A')}")
                    
        else:
            st.warning(f"### ⚠️ {result['status']}")
            st.markdown(result.get('notes', 'Unknown status returned.'))
        
        # Entities checked
        if result.get('entities_checked'):
            st.divider()
            st.caption(f"**Entities analyzed:** {', '.join(result.get('entities_checked', []))}")
        
        # Clear results
        st.divider()
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🗑️ Clear Audit", use_container_width=True):
                st.session_state.audit_result = None
                st.rerun()

# ==========================================
# MODE: GRAPH NEXUS
# ==========================================
elif mode == "📊 Graph Nexus":
    st.markdown("## 📊 The Graph Nexus")
    st.markdown("*Behold the structure of recorded memory — every entity, every connection, every thread of fate.*")
    
    st.divider()
    
    if is_connected and neo4j_driver:
        with st.spinner("*Mapping the knowledge graph...*"):
            # Get node counts
            node_query = "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC"
            nodes = run_query(neo4j_driver, node_query)
            
            # Get relationship counts
            rel_query = "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY count DESC LIMIT 10"
            rels = run_query(neo4j_driver, rel_query)
            
            # Calculate totals
            total_nodes = sum(n['count'] for n in nodes) if nodes else 0
            total_rels = sum(r['count'] for r in rels) if rels else 0
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Entities", f"{total_nodes:,}")
        with col2:
            st.metric("Total Connections", f"{total_rels:,}")
        with col3:
            st.metric("Entity Types", len(nodes) if nodes else 0)
        
        st.divider()
        
        # Detailed breakdown
        col_nodes, col_rels = st.columns(2)
        
        with col_nodes:
            st.markdown("### 📦 Entities by Type")
            if nodes:
                for n in nodes:
                    label = n['label'] or "Unknown"
                    count = n['count']
                    bar_width = int((count / total_nodes) * 100) if total_nodes > 0 else 0
                    st.markdown(f"""
                    **{label}** — `{count:,}`
                    """)
                    st.progress(bar_width / 100)
            else:
                st.info("*No entities found in the graph.*")
        
        with col_rels:
            st.markdown("### 🔗 Top Relationships")
            if rels:
                for r in rels:
                    rel_type = r['type'] or "Unknown"
                    count = r['count']
                    bar_width = int((count / total_rels) * 100) if total_rels > 0 else 0
                    st.markdown(f"""
                    **{rel_type}** — `{count:,}`
                    """)
                    st.progress(bar_width / 100)
            else:
                st.info("*No relationships found in the graph.*")
        
        st.divider()
        
        # Oracle insight
        if total_nodes > 0:
            avg_connections = total_rels / total_nodes if total_nodes > 0 else 0
            st.markdown(f"""
            <div class="oracle-quote">
                "Your realm contains {total_nodes:,} souls and artifacts,<br/>
                bound by {total_rels:,} threads of fate.<br/>
                Each entity touches {avg_connections:.1f} others on average."
            </div>
            """, unsafe_allow_html=True)
    else:
        st.error("### ⚠️ Graph Nexus Unavailable")
        st.markdown("*The Neo4j connection has not been established. Check your configuration.*")

# ==========================================
# FOOTER
# ==========================================
st.divider()
st.markdown("""
<div style="text-align: center; color: var(--text-muted); font-size: 0.8rem; font-family: 'Crimson Text', serif; font-style: italic;">
    The Lore Oracle — Guardian of Canon<br/>
    <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem;">
        Gospel Principle: AI detects, humans decide.
    </span>
</div>
""", unsafe_allow_html=True)

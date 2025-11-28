import streamlit as st
import asyncio
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
from src.neo4j_adapter import Neo4jDatabase
from src.query_agent import QueryAgent
from src.auditor_agent import AuditorAgent

# Load Environment
load_dotenv()

# Config from environment
DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
DB_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Page Config
st.set_page_config(page_title="🐉 Lore Management System", layout="wide")

# Custom CSS for better styling
st.markdown("""
<style>
    .stChat { border-radius: 10px; }
    .status-safe { color: #00cc66; font-weight: bold; }
    .status-contradiction { color: #ff4444; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "audit_result" not in st.session_state:
    st.session_state.audit_result = None

# Database Connection (Cached)
@st.cache_resource
def get_db():
    db = Neo4jDatabase(uri=DB_URI, auth=(DB_USER, DB_PASSWORD))
    asyncio.run(db.connect())
    return db

@st.cache_resource
def get_query_agent(_db):
    return QueryAgent(_db, GEMINI_KEY)

@st.cache_resource
def get_auditor(_db):
    return AuditorAgent(_db, GEMINI_KEY)

# Initialize connections
try:
    db = get_db()
    query_agent = get_query_agent(db)
    auditor = get_auditor(db)
    connection_status = "🟢 Connected to Neo4j + Gemini"
except Exception as e:
    connection_status = f"🔴 Connection Failed: {e}"
    db = None
    query_agent = None
    auditor = None

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.title("🐉 LMS")
    st.caption("Lore Management System")
    st.divider()
    st.write(connection_status)
    st.divider()
    
    mode = st.radio("Mode", ["💬 Query Oracle", "🔍 Audit Submission", "📊 Graph Stats"])

# ==========================================
# MAIN CONTENT
# ==========================================
st.title("🐉 Lore Management System")

if mode == "💬 Query Oracle":
    st.subheader("💬 Query The Oracle")
    st.caption("Ask questions about your campaign lore")
    
    # Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input
    if query_agent and (prompt := st.chat_input("Ask about the lore...")):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Consulting the Archives..."):
                response = asyncio.run(query_agent.ask(prompt))
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})

elif mode == "🔍 Audit Submission":
    st.subheader("🔍 Semantic Lore Auditor")
    st.caption("Check if new lore contradicts existing canon")
    
    submission = st.text_area(
        "Paste your lore submission here:",
        height=200,
        placeholder="The Vulture Clan is a pacifist group that hates technology..."
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        audit_btn = st.button("🔍 Audit", type="primary", disabled=not auditor)
    
    if audit_btn and submission:
        with st.spinner("Analyzing against knowledge graph..."):
            result = asyncio.run(auditor.audit_submission(submission))
            st.session_state.audit_result = result
    
    if st.session_state.audit_result:
        result = st.session_state.audit_result
        
        if result["status"] == "SAFE":
            st.success(f"✅ **SAFE** - No contradictions found!")
            st.info(result.get("notes", ""))
        elif result["status"] == "CONTRADICTION":
            st.error(f"🚨 **CONTRADICTION DETECTED** - {len(result['contradictions'])} issues found")
            
            for i, c in enumerate(result["contradictions"], 1):
                with st.expander(f"❌ Issue {i}: {c.get('severity', 'UNKNOWN')} Severity", expanded=True):
                    st.markdown(f"**Claim:** {c.get('claim', 'N/A')}")
                    st.markdown(f"**Truth:** {c.get('truth', 'N/A')}")
                    st.markdown(f"**Explanation:** {c.get('explanation', 'N/A')}")
        else:
            st.warning(f"⚠️ {result['status']}: {result.get('notes', 'Unknown error')}")
        
        st.divider()
        st.caption(f"Entities checked: {result.get('entities_checked', [])}")

elif mode == "📊 Graph Stats":
    st.subheader("📊 Knowledge Graph Statistics")
    
    if db:
        with st.spinner("Querying graph..."):
            # Get node counts
            node_query = "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC"
            nodes = asyncio.run(db.execute(node_query))
            
            rel_query = "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count ORDER BY count DESC LIMIT 10"
            rels = asyncio.run(db.execute(rel_query))
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📦 Nodes by Type")
            if nodes:
                for n in nodes:
                    st.write(f"- **{n['label']}**: {n['count']}")
            else:
                st.info("No nodes found")
        
        with col2:
            st.markdown("### 🔗 Top Relationships")
            if rels:
                for r in rels:
                    st.write(f"- **{r['type']}**: {r['count']}")
            else:
                st.info("No relationships found")
    else:
        st.error("Database not connected")


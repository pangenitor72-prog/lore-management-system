import streamlit as st
import asyncio
import os
from dotenv import load_dotenv
from neo4j_adapter import Neo4jDatabase
from query_agent import QueryAgent

# Load Environment
load_dotenv()

# Config from environment
DB_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
DB_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# Page Config
st.set_page_config(page_title="LMS: The DM Screen", layout="wide")

# Initialize Session State for Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Database Connection (Cached to prevent reconnecting on every click)
@st.cache_resource
def get_agent():
    db = Neo4jDatabase(
        uri=DB_URI,
        auth=(DB_USER, DB_PASSWORD)
    )
    # Run the async connect in a sync wrapper for Streamlit
    asyncio.run(db.connect())
    return QueryAgent(db, GEMINI_KEY)

try:
    agent = get_agent()
    st.sidebar.success("🟢 Brain Connected")
except Exception as e:
    st.sidebar.error(f"🔴 Connection Failed: {e}")
    agent = None

# ==========================================
# UI LAYOUT
# ==========================================
st.title("🐉 Lore Management System")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("💬 Query The Oracle")
    
    # Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat Input
    if agent and (prompt := st.chat_input("Ask about the lore...")):
        # 1. User Message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. AI Response
        with st.chat_message("assistant"):
            with st.spinner("Consulting the Archives..."):
                # Run the Async Agent in the Sync Streamlit loop
                response = asyncio.run(agent.ask(prompt))
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})

with col2:
    st.subheader("⚙️ Under the Hood")
    
    # Check if we have a response to inspect
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        st.info("Here is what the Agent actually did:")
        
        # We need to hack the agent slightly to expose its thought process
        # Or, simpler: just verify the connection again
        st.success(f"✅ Database Connection: {agent.db.driver is not None}")
        
        # Display the Raw Query (for debugging)
        last_query = st.session_state.messages[-2]["content"]
        st.code(f"User Query: {last_query}", language="text")
        
        st.warning("If the answer was 'Not in Lore', it usually means the Keyword Extractor missed the noun.")
        st.markdown("---")
        st.markdown("**Try typing just the noun:** e.g., 'Vulture Clan' instead of 'Tell me about...'")
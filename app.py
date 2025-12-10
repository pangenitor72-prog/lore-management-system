# app.py (ROOT DIRECTORY)

import streamlit as st
import requests

API_URL = "https://lore-management-system.fly.dev/query"

st.title("Lore Management Dashboard")

try:
    r = requests.post(API_URL, json={"input": "ping"})
    st.success(f"API Response: {r.text}")
except Exception as e:
    st.error(f"Failed to reach API: {e}")

import logging
from typing import Dict, Any

# Import the client library from src
import src.ui.api_client as client

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="MANTLE | Decoherence Engine",
    page_icon="🎲",
    layout="wide"
)

# --- SESSION STATE ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = "session_alpha"

# --- SIDEBAR ---
with st.sidebar:
    st.header("MANTLE Control")
    st.markdown("---")
    
    # FILE UPLOAD
    uploaded_file = st.file_uploader("Ingest Lore (PDF/TXT)", type=["txt", "md"])
    if uploaded_file and st.button("Ingest File"):
        text_content = uploaded_file.read().decode("utf-8")
        try:
            with st.spinner("Ingesting & Vectorizing..."):
                # CLIENT CALL
                result = client.ingest_file(text_content, uploaded_file.name)
                st.success(f"Ingested {result.get('nodes_saved', 0)} nodes!")
        except client.APIClientError as e:
            st.error(f"Ingestion failed: {e}")

# --- MAIN TABS ---
tab_game, tab_lore, tab_graph, tab_audit = st.tabs(["🎲 Game Loop", "📜 Lore Query", "🕸️ Graph", "🛡️ Auditor"])

# === TAB 1: GAME LOOP ===
with tab_game:
    st.subheader("Interactive Roleplay")
    
    # Display Chat History
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input Area
    user_input = st.chat_input("What do you do?")
    if user_input:
        # Add User Message
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Get DM Response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # CLIENT CALL
                    response = client.send_dm_action(user_input, st.session_state.session_id)
                    dm_text = response.get("narrative", "...")
                    st.markdown(dm_text)
                    st.session_state.chat_history.append({"role": "assistant", "content": dm_text})
                    
                    # Optional: Show state updates if available
                    if "state_updates" in response:
                        with st.expander("Debug: State Updates"):
                            st.json(response["state_updates"])
                            
                except client.APIClientError as e:
                    st.error(f"Connection Lost: {e}")

# === TAB 2: LORE QUERY ===
with tab_lore:
    st.subheader("Semantic Knowledge Search")
    query = st.text_input("Ask the Oracle:")
    if st.button("Search Database"):
        try:
            # CLIENT CALL
            results = client.query_lore(query)
            st.write(results)
        except client.APIClientError as e:
            st.error(str(e))

# === TAB 3: GRAPH VISUALIZER ===
with tab_graph:
    if st.button("Refresh Graph"):
        try:
            # CLIENT CALL
            data = client.fetch_graph_data()
            st.json(data) 
        except client.APIClientError as e:
            st.error(str(e))

# === TAB 4: AUDITOR ===
with tab_audit:
    st.subheader("Reality Consistency Check")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("RUN FULL AUDIT"):
            try:
                # CLIENT CALL
                status = client.run_audit()
                st.success("Audit initiated.")
                st.json(status)
            except client.APIClientError as e:
                st.error(str(e))
    
    with col2:
        if st.button("Refresh Pending Issues"):
            try:
                # CLIENT CALL
                issues = client.get_pending_contradictions()
                for issue in issues:
                    with st.expander(f"{issue['severity']} - {issue['description']}"):
                        st.write(issue['evidence'])
                        if st.button(f"Resolve #{issue['id']}", key=issue['id']):
                            client.resolve_contradiction(issue['id'], "Resolved by UI")
                            st.rerun()
            except client.APIClientError as e:
                st.error(str(e))

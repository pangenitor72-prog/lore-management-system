# PROJECT ASSESSMENT: Lore Management System (LMS)

## Date of Assessment: 2025-11-28 (Updated)

## Overall Project Status:
The project is progressing well toward its ultimate goal: **AIRPG** - an AI-powered text-based RPG where an AI Dungeon Master uses this lore system as its memory.

**Current Focus:** Neo4j integration and agentic query capabilities are now functional. The query layer can intelligently extract entities from natural language and retrieve relevant lore context.

## The Big Picture Vision

```
AIRPG (The Game) ← uses ← MANTLE (The DM Engine) ← uses ← LMS (The Memory)
```

- **LMS** = Canonical lore storage (Neo4j graph, World Logic Charter, Gospel Principle)
- **MANTLE** = AI DM personality and rules (DM Prompt v2.3, soft corralling, audacity rewards)
- **AIRPG** = The playable AI RPG experience

---

## Backend Analysis Summary:
-   **Structure:** Well-organized FastAPI application with modular components (services, agents).
-   **Main Application:** `src/api.py` is the primary entry point.
-   **Database:** Uses a Neo4j graph database, with the schema documented in `docs/NEO4J_SCHEMA.md` and managed by `src/neo4j_adapter.py`.
-   **API Routes:** Comprehensive RESTful API is implemented for entities, contradictions, and other core functionalities, defined in `src/api.py` and `src/contradiction_service.py`.
-   **WebSockets:**
    -   An auditor-specific WebSocket endpoint (`/ws/auditor`) exists for event broadcasting.
    -   **CRITICAL MISSING COMPONENT:** The WebSocket endpoint for the main conversational UI (`/ws/gemini`), intended for interaction with the `QueryAgent` (defined in `src/query_agent.py`), is **absent** from `src/api.py`. This is the primary bottleneck for frontend functionality.

---

## Frontend Analysis Summary (loremaster-ui):
-   **Structure:** A standard React application bootstrapped with Vite.
-   **Components:** Basic UI components (`WelcomeScreen`, `ChatInterface`, `UploadContext`, `SearchContext`, `EntityDetailContext`, `ContradictionContext`) have been created, representing different UI "contexts."
-   **State Management:** Relies on React's `useState` and a custom `WebSocketContext` for managing real-time communication.
-   **Styling:** A consistent "Haunting Machine" aesthetic is applied globally via `src/index.css`.
-   **Backend Connection:** A `WebSocketContext` (`src/contexts/WebSocketContext.jsx`) is implemented for managing WebSocket connections and message queuing.
-   **Completeness:** The frontend is currently a visual mockup. The `ChatInterface` and other context components are largely static. There is no logic yet to send user input to the backend or to display real-time data received from the WebSocket.
-   **Functionality:** The frontend cannot perform any core functions (e.g., sending chat messages, displaying dynamic search results, processing uploads) as it is not yet wired to the backend.

---

## Key Issues and Recommendations for a Future Agent:

### **Issue 1: Missing Conversational WebSocket Endpoint on Backend**
-   **Description:** The backend (`src/api.py`) lacks the `/ws/gemini` WebSocket endpoint necessary for the frontend's main conversational interface. The `QueryAgent` in `src/query_agent.py` is designed to handle this interaction, but it's not exposed.
-   **Impact:** The frontend's chat and dynamic context switching cannot function.
-   **Recommendation:** Implement the `/ws/gemini` WebSocket endpoint in `src/api.py`. This endpoint should:
    -   Accept WebSocket connections.
    -   Utilize `src/query_agent.py`'s `handle_websocket` method (or similar logic) to process incoming messages from the frontend.
    -   Send responses back to the frontend via the WebSocket.

### **Issue 2: Frontend Not Wired to Backend Functionality**
-   **Description:** While the frontend has structural components and a `WebSocketContext`, these are not yet connected to actual backend logic for sending or receiving data.
-   **Impact:** The UI is static and non-interactive with the backend.
-   **Recommendation:**
    1.  **Integrate Chat Interface with WebSocket:** Modify `InputArea.jsx` to send user messages via `useWebSocket().sendMessage`. Update `MessageHistory.jsx` to display messages received via `useWebSocket().lastMessage`.
    2.  **Implement Context Switching Logic:** Develop the logic in `App.jsx` to dynamically change the displayed `dynamic-canvas` component (e.g., to `UploadContext`, `SearchContext`, `ContradictionContext`) based on structured messages received from the backend via the WebSocket.
    3.  **Wire Up Context Components:** Connect the specific UI elements within `UploadContext`, `SearchContext`, `EntityDetailContext`, and `ContradictionContext` to their corresponding backend API calls (e.g., file uploads, search queries, contradiction resolution actions) using `fetch` or WebSocket messages as appropriate.

---

## High-Level Next Steps for Development:

### Immediate (Next Session)
1. [ ] Fix blocking Gemini calls in `query_agent.py` (wrap in `run_in_threadpool`)
2. [ ] Fix import inconsistency in `query_agent.py` (use relative import for audit_log)

### Short-Term (LMS Phase XII)
3. [ ] Polish Streamlit UI for a fun DM experience
4. [ ] Implement `/ws/gemini` WebSocket endpoint for React frontend
5. [ ] Add party knowledge filtering to graph queries

### Medium-Term (LMS Phase XV - Pre-AIRPG Bridge)
6. [ ] Stable JSON API for external clients (AIRPG)
7. [ ] Session event logging (record what happens during gameplay)
8. [ ] Timeline-based event storage

### Long-Term (AIRPG Track 2)
9. [ ] DM Agent v0.1 using MANTLE personality (DM PROMPT v2.3)
10. [ ] Scene and dialogue generation
11. [ ] Basic action resolution with Modified Rule of Cool

---

## Technical Status (2025-11-28)

| Component | Status | File(s) |
|-----------|--------|---------|
| Neo4j Adapter | ✅ Working | `src/neo4j_adapter.py` |
| Entity Ingestor | ✅ Working | `src/ingestor.py` |
| QueryAgent (RAG) | ✅ Enhanced | `src/query_agent.py` - 3-tier agentic retrieval |
| AuditorAgent | ✅ Working | `src/auditor_agent.py` |
| Streamlit UI | 🟡 Basic | `app.py` |
| React UI | ❌ Shell | `loremaster-ui/` |
| WebSocket `/ws/gemini` | ❌ Missing | Needed in `src/api.py` |

---

This assessment should provide a clear roadmap for any future agent to continue development effectively.

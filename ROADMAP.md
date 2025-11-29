# 🗺️ The Lore Oracle Roadmap

This document outlines the strategic evolution of the Lore Oracle from a passive knowledge base to an active AI Dungeon Master system.

## 🟢 Phase XII: The Foundation (Current Status)
**Goal:** Establish a robust memory layer and query interface.
- [x] **Neo4j Graph Database:** Entities and relationships stored natively.
- [x] **"Haunting Machine" UI:** Streamlit interface with thematic styling.
- [x] **AI Ingestion:** Upload text/lore files -> Auto-extract entities to graph.
- [x] **The Oracle (RAG):** Natural language Q&A using 4-tier retrieval strategy.
- [x] **Graph Nexus:** Interactive visualization of the knowledge graph.
- [x] **Truth Auditor:** Verify new lore against established canon.

---

## 🟡 Phase XIII: The Active Session (Next Priority)
**Goal:** Transform the tool from a wiki into a live Game Master's assistant.

### 1. Session State Manager
- [ ] Create a **"Game Session"** mode in the sidebar.
- [ ] Track **Active Scene Context** (Who is here? Where are we? What time is it?).
- [ ] Maintain a running "Campaign Log" that updates the graph in real-time.

### 2. Live World Updates
- [ ] **Natural Language Action Parsing:**
    - Input: *"The party kills Kael."*
    - System: Proposes update `SET n.status = 'Dead'` for node `Kael`.
- [ ] **Quick-Add Entity:** "Generate NPC: Shopkeeper, Gnome, suspicious" -> Instantly adds to graph and displays stats.

### 3. Rules & Mechanics Integration
- [ ] **Dice Roller:** 3D dice in the UI or simple command `/roll 2d20`.
- [ ] **Rules Oracle:** Index the SRD (System Reference Document) so the AI can answer rules questions ("Grappling rules") alongside lore questions.

---

## 🔵 Phase XIV: The Senses (Multi-Modal)
**Goal:** Expand input/output capabilities beyond text.

### 1. Voice of the Oracle
- [ ] **Text-to-Speech (TTS):** The Oracle reads lore descriptions aloud in a distinct, haunting voice.
- [ ] **Speech-to-Text (STT):** Dictate notes or dialogue directly to the system.

### 2. The Cartographer's Eye
- [ ] **Map Analysis:** Upload an image of a fantasy map.
- [ ] **Visual Extraction:** AI identifies "Forest," "Castle," "Road" and creates Location nodes with spatial relationships.

---

## 🟣 Phase XV: The Living World (Simulation)
**Goal:** The world acts on its own when players aren't looking.

### 1. Faction Turns
- [ ] **Background Simulation:** Between sessions, the AI reviews Faction goals.
- [ ] **Event Generation:** "The Vulture Clan attacks the Iron Brotherhood." -> Generates `Event` nodes and updates relationships.

### 2. Quest Generator
- [ ] **Loose End Detector:** Scan graph for unresolved plot hooks.
- [ ] **Procedural Missions:** Generate quest prompts based on players' current location and enemies.

---

## ☁️ Deployment Strategy
- **Database:** Neo4j AuraDB (Cloud Managed)
- **Application:** Streamlit Community Cloud
- **Access:** Shared URL for DM (and potentially players with restricted view).


# LORE MANAGEMENT SYSTEM (LMS) & AIRPG — MASTER ROADMAP
**Author:** Shawn King  
**Project:** Lore Management System → MANTLE Engine → AIRPG  
**Purpose:** Provide a clear, modular development strategy from LMS completion to full AI-driven RPG engine.

---

# 🔷 OVERVIEW
This roadmap is divided into two major tracks:

1. **Lore Management System (LMS)** — the canonical backend tool for building, storing, validating, and maintaining world lore.
2. **AIRPG Engine** — the large-scale AI-driven game engine built *on top* of LMS, using the LMS as its memory and canon authority.

Each phase is designed to be:
- Modular  
- Incremental  
- Usable as soon as completed  
- Expandable without rewrites  
- Easy to track in GitHub Projects  

---

# ===========================================================
# 🔵 TRACK 1 — LORE MANAGEMENT SYSTEM (LMS)
# ===========================================================

The goal of Track 1 is to deliver a **fully usable tool for Jim**, and then prepare the system for AIRPG integration.

---

# ⭐ PHASE XII — UI, UX & TEST SUITE (ACTIVE PHASE)
**Goal:** Deliver a polished, usable, daily tool for Jim.

### Deliverables
- **Entity Browser UI**  
- **Contradiction Resolution UI**  
- **Batch Document Processor**
- **WebSocket live-update indicators**
- **Accessibility + visual polish**
- **Test Suite (75+ tests)**

### Outcomes
- Jim can browse and edit lore comfortably  
- Live contradictions + updates are visible  
- System stability is locked in for production  

---

# ⭐ PHASE XIII — Canon Management & Charter Law
**Goal:** Introduce the rules that govern how the world accepts or rejects information.**

### Deliverables
- Charter Law validation system  
- Hard overrides (DM forces truth)  
- Soft overrides (preferred truth)
- Annotated contradiction reasons  
- Confidence-level system  

### Outcomes
- Jim becomes the **arbiter of canon**  
- The system automatically enforces world logic  

---

# ⭐ PHASE XIV — Campaign Profiles & Modular Storage
**Goal:** Allow multiple campaigns to share global canon while diverging locally.**

### Deliverables
- Per-campaign profiles  
- Per-campaign overrides  
- NPC and Faction state separation  
- Snapshot export (per campaign)

### Outcomes
- Multiple campaigns, one world  
- No accidental overwriting of global lore  

---

# ⭐ PHASE XV — Pre-AIRPG Integration Layer
**Goal:** Turn LMS into a stable backend for AIRPG without losing standalone usability.**

### Deliverables
- Stable JSON API for external clients  
- Read-only and read-write modes  
- “Lore Snapshot” exports  
- Timeline-based event storage  
- API rate-limiting & request shaping  

### Outcomes
- LMS becomes the **world brain** of AIRPG  
- Safe, controlled two-way communication  

---

# ===========================================================
# 🟣 TRACK 2 — AIRPG ENGINE (THE BIG PROJECT)
# ===========================================================

AIRPG is built *after* LMS is complete and in Jim’s hands.

The engine is modular:  
**a thin playable loop first, then expansion packs added layer by layer.**

---

# ⭐ PHASE I — Minimal Playable Prototype (MVP)
**Goal:** Create a playable, text-based AIRPG demo.**

### Deliverables
- DM Agent v0.1  
- Scene + dialogue generation  
- Basic action resolution  
- Session-local memory  
- Simple text UI  
- LMS read/write bridge  

### Outcomes
- First playable experience  
- “Holy shit it works” moment  
- Real feedback loop for design  

---

# ⭐ PHASE II — NPC Personality Engine (OCEAN)
**Goal:** Give NPCs distinct, consistent personalities.**

### Deliverables
- OCEAN personality scores  
- Motivations + emotional state  
- Dialogue style modifiers  
- Behavioral rules  

### Outcomes
- NPCs feel alive and predictable  
- Deep player-NPC interaction potential  

---

# ⭐ PHASE III — World Simulation Layer (Tick Engine)
**Goal:** Add time, change, and consequences.**

### Deliverables
- Tick-based event propagation  
- NPC daily routines  
- Rumor network  
- Weather hooks  
- Faction influence drift  
- Economy/decay systems  

### Outcomes
- World becomes **alive between sessions**  
- Player actions cause cascading effects  

---

# ⭐ PHASE IV — Graph Database Integration
**Goal:** Give the world actual structure, causality, and meaningful relationships.**

### Deliverables
- Full relationship graph  
- Event ancestry tree  
- Influence webs  
- Faction hierarchy graphs  
- Migration layer LMS → Graph  

### Outcomes
- The world becomes causally intelligent  
- Multi-hop reasoning becomes possible  

---

# ⭐ PHASE V — Vector Database Integration (Semantic Memory)
**Goal:** Give AIRPG an understanding of meaning, tone, and narrative coherence.**

### Deliverables
- Lore embeddings  
- Narrative similarity search  
- NPC personality embeddings  
- Quest generator using vector+graph fusion  

### Outcomes
- Stories feel *inevitable*, not random  
- Quest & scene generation becomes grounded  

---

# ⭐ PHASE VI — DM Agent v2.0 (The Real Dungeon Master)
**Goal:** Build the full orchestration layer of the AIRPG experience.**

### Deliverables
- Rule enforcement  
- Canon checks  
- Scene pacing  
- Narrative arc tracking  
- Recap system  
- Long-term memory management  

### Outcomes
- AI GM feels human—or better  
- Campaigns become coherent and long-lived  

---

# ⭐ PHASE VII — Player Interface (Frontend Client)
**Goal:** A dedicated interface for players.**

### Options
- Web UI  
- Chat-style interface  
- Terminal-based  
- Mobile app  
- Voice interface  

### Outcomes
- AIRPG becomes a real product  
- Multi-player campaigns become possible  

---

# ===========================================================
# 🔶 DEVELOPMENT PHILOSOPHY
# ===========================================================

### ✔ Build small → Integrate → Expand  
You don’t build the entire engine first.  
You build the **core loop**, then add systems like organs.

### ✔ LMS is the spine  
It must be completed, polished, and in Jim’s hands before AIRPG begins.

### ✔ Modular layers  
Graph and vector DBs are *Phase IV and Phase V* integrations, not early requirements.

### ✔ Nothing wasted  
Every phase builds directly on the one before it.

---

# ===========================================================
# 🔷 IMPLEMENTATION STRATEGY FOR GITHUB
# ===========================================================

### 🅰 Markdown Roadmap (this file)  
This is the **single source of truth**.  
Long-term vision, all phases, full context.

### 🅱 GitHub Project Board  
Only the **current active phase** appears on the board:
- To Do  
- In Progress  
- Review  
- Done  

Archive and recreate the board each phase.

### 🅲 GitHub Issues  
Create issues only from active deliverables.  
This keeps the board clean and prevents cognitive overload.

---

# END OF ROADMAP

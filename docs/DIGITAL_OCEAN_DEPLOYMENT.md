# LMS / MANTLE — Production Deployment Handoff Dossier (v1.0.1)

**Environment:** DigitalOcean Ubuntu 22.04 LTS
**Maintainer:** Shawn King
**Prepared by:** Metis
**Date:** December 2, 2025

## 1️⃣ SYSTEM OVERVIEW — FULL STACK
The system is a three-tier production deployment:

### A. Backend API — FastAPI + Uvicorn + Systemd
*   **Path:** `/opt/lms/lore-management-system/`
*   **Virtualenv:** `/opt/lms/lore-management-system/venv/`
*   **Entry:** `src.api:app`
*   **Port:** `8000` (internal-only)
*   **Service:** `lms-api.service`
*   **Responsibilities:** Entity creation, update, retrieval, file ingestion, Smart Ingestor entrypoint, Contradiction detection / Auditor Agent, Neo4j graph driver, Vector index initialization, WebSocket broadcaster (for audit events).
*   **Key note:** Uses `systemd` to run Uvicorn as a resilient, auto-restarting service.

### B. Graph Database — Neo4j 5.12 (Docker)
*   **Container:** `neo4j_db`
*   **Ports:** `7474` (Neo4j Web UI), `7687` (Bolt protocol)
*   **Data directory:** `/opt/lms/neo4j_data/` (persisted)
*   **Password:** Stored locally (not committed to server)
*   **Responsibilities:** Stores all entities, nodes, edges, embedding vectors, temporal + relationship graph structure, foundation for Smart Ingestor & Decoherence Engine.
*   **Key improvements now deployed:** APOC plugin enabled, Vector index creation compatible with Neo4j 5.x, Auth enabled, Stable bolt connectivity verified.

### C. Frontend — Vite → NGINX
*   **Build path:** `/opt/lms/frontend/`
*   **Files served:** `index.html`, `/assets/*`
*   **Served at:** `https://<your-server-ip-or-domain>/`
*   **Proxy route:** `/api → 127.0.0.1:8000`
*   **Key note:** Clean, stable SPA deployment.

## 2️⃣ INFRASTRUCTURE CONFIG — WHAT’S ON YOUR SERVER

### NGINX
*   **File:** `/etc/nginx/sites-available/lms-frontend` (enabled via symlink into `/etc/nginx/sites-enabled/`)
*   **Handles:** Static file serving, routing fallback via `try_files`, `/api` → backend proxy, `gzip` (if enabled later), SSL once Certbot is run.
*   **Important:** Default site was removed to prevent routing pollution.

### Systemd Services
*   **`lms-api.service`**: Already deployed exactly as needed.
*   **Neo4j**: Not a systemd service, launched via Docker. (Might want a `neo4j-docker.service` later for robustness).

## 3️⃣ WHAT WE COMPLETED (DETAILED)
Step-by-step chain to operational server:
1.  Installed Neo4j 5.12 (Docker).
2.  Solved Vector Index Errors: Invalid input 'VECTOR' resolved by using Neo4j 5.x, correcting index creation syntax, enabling APOC, and ensuring container restart without losing config.
3.  Backend API successfully connects to Neo4j: Resolved `RuntimeError: Neo4j connection failed` issues (wrong Neo4j version, Bolt port conflicts, password misconfig, adapter retry logic).
4.  Created systemd service for Uvicorn: Fixed service dying, inability to restart backend, and `--reload` conflicts.
5.  Frontend built, deployed, and served by NGINX: Solved missing Vite build files, incorrect root path, `dist/` not copied, default NGINX config clash, missing symlink.
6.  Reverse proxy working: Verified `/api` → local FastAPI, `/assets/*` → static files, `/` → `index.html`.

## 4️⃣ WHAT REMAINS TO BE DONE — PRIORITIZED
1.  **HTTPS / SSL**: Mandatory. Use `certbot`.
2.  **UFW Firewall Lockdown**: Mandatory. `sudo ufw allow 22`, `80`, `443`, then `sudo ufw enable`.
3.  **API & Neo4j Health Endpoints**: For monitoring, deployment automation, uptime systems.
4.  **Logging Improvements**: Centralize logs, rotate Uvicorn logs, log frontend access/errors, persist Neo4j logs outside container.
5.  **Automated Deployment**: (Later) GitHub Actions SSH deploy, auto-build frontend, auto-restart backend on push.

## 5️⃣ PROBLEMS FACED — FINAL DIAGNOSTIC RECORD
*   **Problem 1 — Vite Build Failure**: Node version mismatch, corrupted dependency lock. Fix: Delete `node_modules`, reinstall, rebuild.
*   **Problem 2 — “Port 7687 already in use”**: Zombie Neo4j container. Fix: Forcibly removed, recreated container.
*   **Problem 3 — API boot loop**: Connection attempt during lifespan. Fix: Ensure Neo4j ready before API boot, unify env config.
*   **Problem 4 — NGINX not serving files**: Wrong root dir, default site conflict. Fix: Correct path, remove default, create symlink.
*   **Problem 5 — External API unreachable**: Uvicorn bound to 127.0.0.1. Fix: `--host 0.0.0.0`.

## 6️⃣ DIRECTORY MAP (FINAL)
*   `/opt/lms/`
    *   `frontend/` (`index.html`, `assets/`, ...)
    *   `lore-management-system/` (`venv/`, `src/`, `tests/`)
    *   `neo4j_data/` (`logs/`, `data/`, `import/`)
*   `/etc/nginx/`
    *   `sites-available/lms-frontend`
    *   `sites-enabled/lms-frontend`
*   `/etc/systemd/system/`
    *   `lms-api.service`

## 7️⃣ VARIABLES YOU MUST STORE LOCALLY
*   `NEO4J_PASSWORD`
*   `NEO4J_URI`
*   `API_SECRET_KEY`
*   `EMBEDDING_API_KEY`
*   `LMS_ENV`
*   `SSL_CERT_PATH`
*   `SSL_KEY_PATH`

## 8️⃣ FINAL STATUS — PRODUCTION READY
*   **Backend API**: ✅ online, stable under systemd.
*   **Neo4j 5.12**: ✅ online, vector index created.
*   **Frontend**: ✅ live, served via nginx.
*   **Reverse Proxy**: ✅ working, /api verified.
*   **Security**: ⚠ pending, needs SSL + UFW.
*   **Automation**: ⏳ later, not needed yet.

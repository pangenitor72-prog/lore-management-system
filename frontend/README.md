# Frontend - IMPORTANT ARCHITECTURE NOTE

## TWO FRONTENDS - READ THIS FIRST

This project has **TWO separate frontend systems**:

### 1. Production UI (Static HTML)
- **Location:** `frontend/dist/index.html`
- **Description:** Self-contained 16k-line HTML/CSS/JS file
- **Features:** Raven logo landing page, "Mantle - Your Story Awaits"
- **Served at:** http://localhost:8000 (via FastAPI)
- **Edit directly:** Yes, modify index.html for production changes

### 2. React Prototype (Development Only)
- **Location:** `frontend/src/`
- **Description:** React components for prototyping
- **Builds to:** `frontend/dist-react/` (NOT dist/)
- **Status:** Prototype/experimental, not served in production

## CRITICAL: Don't Overwrite Production UI

The Vite config outputs to `dist-react/` to prevent overwriting the production UI.

If `dist/index.html` ever gets corrupted:
```bash
git restore frontend/dist/
```

## Production UI Structure (dist/)

```
dist/
├── index.html          # Main production app (16k lines)
├── assets/             # JS/CSS assets
├── images/             # Raven mascot image
└── icons/              # PWA icons
```

Key screens in index.html (search for `class="screen"`):
- `invite-code` - Entry invite code
- `playtester-welcome` - Welcome for testers
- `ingest` - World selection & lore import
- `setup` - Story setup
- `story` - Main gameplay
- `graph` - Knowledge graph visualization
- `admin` - Admin panel

## React Prototype Structure (src/)

```
src/
├── components/
│   ├── ChatInterface.jsx    # Chat UI
│   ├── Dashboard.jsx        # Auditor dashboard
│   ├── WorldManager.jsx     # World management (prototype)
│   └── game/                # Game components
├── contexts/
│   └── WebSocketContext.jsx
├── hooks/
│   ├── useChat.js
│   └── useAuditor.js
├── styles/
│   └── globals.css
├── App.jsx
└── main.jsx
```

## Development Commands

```bash
# React dev server (port 3000) - for prototyping only
npm run dev

# Build React to dist-react/ (safe - won't touch production)
npm run build
```

## Making Production Changes

To modify the production UI:
1. Edit `frontend/dist/index.html` directly
2. Restart the FastAPI server to see changes
3. No build step required

## API Integration

All game API endpoints use `/api/game/...` prefix:
- `/api/game/lore-bases` - List worlds
- `/api/game/session` - Create game session
- `/api/game/lore-bases/{id}/preview` - Preview entity extraction

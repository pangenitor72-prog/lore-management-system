# Frontend Architecture

## Two Frontend Systems - READ THIS FIRST

This project has **TWO separate frontend systems**. Understanding this prevents a recurring issue where the production UI gets overwritten.

### 1. Production UI (Static HTML)
- **Location:** `frontend/dist/index.html`
- **Description:** Self-contained ~17k-line HTML/CSS/JS file
- **Features:** Raven mascot landing page, "Mantle - Your Story Awaits"
- **Served at:** https://lore-management-system.fly.dev/ (via FastAPI)
- **Edit directly:** Yes, modify index.html for production changes

### 2. React Prototype (Development Only)
- **Location:** `frontend/src/`
- **Description:** React components for prototyping new features
- **Builds to:** `frontend/dist-react/` (NOT dist/)
- **Status:** Development/experimental only, not served in production

## CRITICAL: Don't Overwrite Production UI

The Vite config outputs to `dist-react/` to prevent overwriting the production UI.

If `dist/index.html` ever gets corrupted or replaced:
```bash
git restore frontend/dist/
```

## Production UI Structure (dist/)

```
dist/
├── index.html          # Main production app (~17k lines)
├── sw.js               # Service worker (PWA support)
├── manifest.json       # PWA manifest
├── assets/             # Built JS/CSS assets
├── images/
│   └── raven.png       # Mascot image (oval gold frame)
└── icons/              # PWA icons (various sizes)
```

## Design System: Obsidian & Gold

The production UI uses the **Obsidian & Gold** design system:

### CSS Variables (defined in :root)
```css
/* Colors */
--bg-primary: #0f0f12;
--bg-secondary: #16161a;
--bg-card: #1c1c21;
--accent-gold: #D4AF37;
--accent-warm: #c9a55c;

/* Typography */
--font-narrative: 'Crimson Pro', Georgia, serif;
--font-ui: 'JetBrains Mono', 'Fira Code', monospace;

/* Border Radii */
--radius-sharp: 4px;
--radius-medium: 8px;
--radius-soft: 12px;
```

### Visual Features
- Noise texture overlay for premium feel
- Inner depth shadows on cards
- Subtle vignette effect
- Metallic gold accents
- Oval frame on raven mascot

## Key Screens (in index.html)

Search for `class="screen"` to find each screen:

| Screen ID | Purpose |
|-----------|---------|
| `invite-code` | Beta access code entry |
| `playtester-welcome` | Welcome message for testers |
| `start` | Main landing with mode selection cards |
| `world-builder` | World creation flow |
| `ingest` | Lore import with file explorer |
| `setup` | Story/character setup |
| `story` | Main gameplay interface |
| `graph` | Knowledge graph visualization |
| `admin` | Admin panel |

## Key UI Components

### File Explorer (in ingest screen)
- Drag & drop files or folders
- File tree with checkboxes
- Preview individual files
- Supports: .txt, .md, .json, .pdf

### Entity Review Panel (Human-in-the-Loop)
- AI extracts entities from lore
- Users review and select which to keep
- Edit entity names/descriptions inline
- Filter by entity type
- Bulk select/deselect

### Character Creation
- Guided flow with genre-specific options
- Archetype selection
- Equipment choices
- Background generation

## React Prototype Structure (src/)

```
src/
├── App.jsx              # Main app component
├── main.jsx             # Entry point
├── components/
│   ├── ChatInterface.jsx
│   ├── Dashboard.jsx
│   ├── WorldManager.jsx
│   └── game/            # Game components
├── contexts/
│   └── WebSocketContext.jsx
├── hooks/
│   ├── useChat.js
│   └── useAuditor.js
└── styles/
    └── globals.css      # Design tokens
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
2. Restart the FastAPI server to see changes locally
3. Deploy with `fly deploy --now`
4. No build step required

## API Integration

All game API endpoints use `/api/game/...` prefix:

| Endpoint | Purpose |
|----------|---------|
| `GET /api/game/lore-bases` | List available worlds |
| `POST /api/game/session` | Create game session |
| `POST /api/game/lore-bases/{id}/preview` | Preview entity extraction |
| `POST /api/game/lore-bases` | Commit approved entities |
| `GET /api/version` | Get current app version |

## File Explorer Usage (for Jim)

1. Navigate to **World Creator** → **Import Your Own**
2. **Add Files:**
   - Click "+ Add Files" to browse
   - Click "+ Add Folder" to add entire folder
   - Or drag & drop files/folders onto the drop zone
3. **Manage Files:**
   - Files appear in a list with checkboxes
   - Toggle checkboxes to include/exclude
   - Click "Preview" to see file contents
   - Click X to remove a file
4. **Import:**
   - Click "Preview Extraction" to analyze
   - Review extracted entities (edit/select/deselect)
   - Click "Import Selected Entities" to save

Supported formats: `.txt`, `.md`, `.json`, `.pdf`

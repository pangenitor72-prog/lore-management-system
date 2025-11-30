# Lore Management System - Frontend

React frontend for the Lore Management System, providing a real-time chat interface for lore queries and a dashboard for monitoring auditor events.

## Architecture

```
src/
├── contexts/
│   └── WebSocketContext.jsx   # Global WebSocket connection manager
├── hooks/
│   ├── useChat.js             # Chat state & query_events handler
│   └── useAuditor.js          # Dashboard state & auditor_events handler
├── components/
│   ├── ChatInterface.jsx      # Lore Oracle chat UI
│   └── Dashboard.jsx          # Auditor dashboard UI
├── styles/
│   └── globals.css            # Design tokens & base styles
├── App.jsx                    # Main app with routing
└── main.jsx                   # Entry point
```

## WebSocket Channels

The frontend connects to `ws://localhost:8000/ws/events` and subscribes to:

| Channel | Purpose | Consumer |
|---------|---------|----------|
| `query_events` | Chat responses from QueryAgent | `useChat` hook |
| `auditor_events` | Contradiction detection, audit notifications | `useAuditor` hook |
| `ingestion_events` | File processing progress | (Future) |

## Quick Start

```bash
# Install dependencies
cd frontend
npm install

# Start dev server (connects to backend at localhost:8000)
npm run dev
```

The frontend will be available at `http://localhost:3000`.

## Message Formats

### Query Events (Chat)

**Sending a query:**
```json
{
  "_channel": "query_events",
  "type": "query",
  "content": "Who is the Black King?",
  "message_id": "msg-123"
}
```

**Receiving responses:**
```json
{
  "_channel": "query_events",
  "type": "streaming_chunk",
  "content": "The Black King is...",
  "message_id": "msg-123"
}
```

### Auditor Events (Dashboard)

```json
{
  "_channel": "auditor_events",
  "type": "new_contradiction",
  "data": {
    "contradiction_id": 101,
    "severity": "CRITICAL",
    "description": "Timeline fracture detected",
    "entity_ids": ["char-abc123", "event-def456"]
  },
  "timestamp": "2025-11-30T10:30:00Z"
}
```

## Design System

The UI uses a dark fantasy theme with CSS custom properties:

- **Colors**: Deep charcoal backgrounds with amber gold accents
- **Typography**: Crimson Pro (display), JetBrains Mono (code)
- **Components**: Card-based layout with subtle borders and glow effects

See `src/styles/globals.css` for the full token reference.


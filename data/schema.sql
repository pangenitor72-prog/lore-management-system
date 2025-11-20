-- Lore Management System Database Schema
-- Version: 1.3
-- Date: 2025-11-20
-- Fixed: Consolidated all table definitions into a single, final, canonical version.

-- Entities table (all lore objects)
CREATE TABLE IF NOT EXISTS entities (
    canon_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('Character', 'Location', 'Faction', 'Event', 'Item', 'Concept')),
    canonical_name TEXT NOT NULL,
    approval_status TEXT NOT NULL CHECK(approval_status IN ('APPROVED', 'PENDING', 'REJECTED')),
    confidence_level TEXT NOT NULL CHECK(confidence_level IN ('CONFIRMED', 'PROBABLE', 'SPECULATIVE', 'UNCERTAIN')),
    party_knowledge TEXT NOT NULL CHECK(party_knowledge IN ('KNOWN', 'RUMORED', 'SECRET', 'FORGOTTEN')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Approved fields (canonical attributes)
CREATE TABLE IF NOT EXISTS approved_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canon_id TEXT NOT NULL,
    field_key TEXT NOT NULL,
    field_value TEXT NOT NULL,
    FOREIGN KEY (canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE
);

-- Aliases for entities
CREATE TABLE IF NOT EXISTS aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canon_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    FOREIGN KEY (canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE
);

-- Relationships between entities
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_canon_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    to_canon_id TEXT NOT NULL,
    confidence_level TEXT NOT NULL CHECK(confidence_level IN ('CONFIRMED', 'PROBABLE', 'SPECULATIVE', 'UNCERTAIN')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE,
    FOREIGN KEY (to_canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE
);

-- Revision history (for temporal tracking)
CREATE TABLE IF NOT EXISTS revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canon_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT,
    FOREIGN KEY (canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE
);

-- Contradictions detected by Auditor
CREATE TABLE IF NOT EXISTS contradictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contradiction_id TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'IN_REVIEW', 'RESOLVED', 'DISMISSED')),
    detected_at TEXT NOT NULL,
    entity_a_id TEXT,
    entity_b_id TEXT,
    contradiction_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('HIGH', 'MEDIUM', 'LOW')),
    description TEXT NOT NULL,
    evidence TEXT NOT NULL, -- Stored as JSON text
    confidence REAL,
    scoring_reasoning TEXT,
    possible_resolutions TEXT, -- Stored as JSON text
    resolution_notes TEXT,
    updated_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_a_id) REFERENCES entities (canon_id) ON DELETE CASCADE,
    FOREIGN KEY (entity_b_id) REFERENCES entities (canon_id) ON DELETE CASCADE
);

-- Many-to-many table for multi-entity contradictions
CREATE TABLE IF NOT EXISTS contradiction_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contradiction_id TEXT NOT NULL,
    canon_id TEXT NOT NULL,
    FOREIGN KEY (contradiction_id) REFERENCES contradictions(contradiction_id) ON DELETE CASCADE,
    FOREIGN KEY (canon_id) REFERENCES entities(canon_id) ON DELETE CASCADE
);

-- Triage analysis provided by AI or human reviewers
CREATE TABLE IF NOT EXISTS triage_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contradiction_id TEXT UNIQUE, -- One analysis per contradiction
    analyst TEXT NOT NULL,
    analysis TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    confidence TEXT NOT NULL CHECK(confidence IN ('HIGH', 'MEDIUM', 'LOW')),
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (contradiction_id) REFERENCES contradictions(contradiction_id) ON DELETE CASCADE
);

-- Log for interactions with the query agent
CREATE TABLE IF NOT EXISTS agent_chat_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_status ON entities(approval_status);
CREATE INDEX IF NOT EXISTS idx_approved_fields_canon ON approved_fields(canon_id);
CREATE INDEX IF NOT EXISTS idx_approved_fields_key ON approved_fields(field_key);
CREATE INDEX IF NOT EXISTS idx_aliases_canon ON aliases(canon_id);
CREATE INDEX IF NOT EXISTS idx_relationships_from ON relationships(from_canon_id);
CREATE INDEX IF NOT EXISTS idx_relationships_to ON relationships(to_canon_id);
CREATE INDEX IF NOT EXISTS idx_revisions_canon ON revisions(canon_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_status ON contradictions(status);
CREATE INDEX IF NOT EXISTS idx_contradictions_severity ON contradictions(severity);
CREATE INDEX IF NOT EXISTS idx_contradiction_entities_canon ON contradiction_entities(canon_id);

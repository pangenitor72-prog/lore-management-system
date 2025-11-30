import { useState, useEffect } from 'react'
import { useAuditor } from '../hooks/useAuditor'
import { useWebSocket, ConnectionState } from '../contexts/WebSocketContext'
import './Dashboard.css'

/**
 * Dashboard Component
 * 
 * Real-time DM dashboard showing active contradictions, 
 * audit events, and system health. Consumes auditor_events
 * via WebSocket for live updates.
 */

const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, MINOR: 4 }

export function Dashboard() {
  const { 
    contradictions, 
    recentEvents, 
    isAuditing, 
    stats, 
    newCount,
    markAsSeen,
    isConnected 
  } = useAuditor()
  
  const { connectionState } = useWebSocket()
  const [selectedContradiction, setSelectedContradiction] = useState(null)
  const [filterSeverity, setFilterSeverity] = useState('ALL')

  // Sort contradictions by severity and newness
  const sortedContradictions = [...contradictions]
    .filter(c => filterSeverity === 'ALL' || c.severity === filterSeverity)
    .sort((a, b) => {
      if (a.isNew !== b.isNew) return a.isNew ? -1 : 1
      return (SEVERITY_ORDER[a.severity] || 5) - (SEVERITY_ORDER[b.severity] || 5)
    })

  const handleContradictionClick = (contradiction) => {
    setSelectedContradiction(contradiction)
    if (contradiction.isNew) {
      markAsSeen(contradiction.contradiction_id)
    }
  }

  const getSeverityClass = (severity) => {
    return `severity--${(severity || 'unknown').toLowerCase()}`
  }

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return '—'
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    })
  }

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="dashboard-header">
        <div className="dashboard-header__title">
          <span className="dashboard-header__icon">🛡️</span>
          <h1>Auditor Dashboard</h1>
          {isAuditing && (
            <span className="audit-badge">
              <span className="audit-badge__spinner" />
              Auditing...
            </span>
          )}
        </div>
        <div className="dashboard-header__status">
          <span className={`status-dot ${connectionState === ConnectionState.CONNECTED ? 'status-dot--connected' : ''}`} />
          <span>{connectionState === ConnectionState.CONNECTED ? 'Live' : 'Offline'}</span>
        </div>
      </header>

      {/* Stats Bar */}
      <div className="dashboard-stats">
        <div className="stat-card">
          <div className="stat-card__value">{stats.totalContradictions}</div>
          <div className="stat-card__label">Total Issues</div>
        </div>
        <div className="stat-card stat-card--warning">
          <div className="stat-card__value">{stats.pendingCount}</div>
          <div className="stat-card__label">Pending</div>
        </div>
        <div className="stat-card stat-card--danger">
          <div className="stat-card__value">{stats.criticalCount}</div>
          <div className="stat-card__label">Critical</div>
        </div>
        {newCount > 0 && (
          <div className="stat-card stat-card--accent">
            <div className="stat-card__value">{newCount}</div>
            <div className="stat-card__label">New</div>
          </div>
        )}
      </div>

      <div className="dashboard-content">
        {/* Contradictions List */}
        <section className="dashboard-panel contradictions-panel">
          <div className="panel-header">
            <h2>Active Issues</h2>
            <div className="panel-header__filters">
              <select 
                value={filterSeverity} 
                onChange={(e) => setFilterSeverity(e.target.value)}
                className="severity-filter"
              >
                <option value="ALL">All Severities</option>
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
                <option value="MINOR">Minor</option>
              </select>
            </div>
          </div>

          <div className="contradictions-list">
            {sortedContradictions.length === 0 ? (
              <div className="empty-state">
                <span className="empty-state__icon">✨</span>
                <p>No contradictions detected</p>
                <span className="empty-state__hint">
                  {isConnected ? 'The lore is consistent... for now.' : 'Connect to see live updates'}
                </span>
              </div>
            ) : (
              sortedContradictions.map((contradiction) => (
                <div
                  key={contradiction.contradiction_id}
                  className={`contradiction-card ${
                    selectedContradiction?.contradiction_id === contradiction.contradiction_id 
                      ? 'contradiction-card--selected' 
                      : ''
                  } ${contradiction.isNew ? 'contradiction-card--new' : ''}`}
                  onClick={() => handleContradictionClick(contradiction)}
                >
                  {contradiction.isNew && (
                    <span className="new-badge">NEW</span>
                  )}
                  <div className="contradiction-card__header">
                    <span className={`severity-badge ${getSeverityClass(contradiction.severity)}`}>
                      {contradiction.severity}
                    </span>
                    <span className="contradiction-card__type">
                      {contradiction.contradiction_type || 'Unknown'}
                    </span>
                  </div>
                  <p className="contradiction-card__description">
                    {contradiction.description || 'No description available'}
                  </p>
                  <div className="contradiction-card__meta">
                    <span className="contradiction-card__id">
                      #{contradiction.contradiction_id}
                    </span>
                    <span className="contradiction-card__time">
                      {formatTimestamp(contradiction.detected_at || contradiction.receivedAt)}
                    </span>
                  </div>
                  {contradiction.entity_ids?.length > 0 && (
                    <div className="contradiction-card__entities">
                      {contradiction.entity_ids.map((id, i) => (
                        <span key={i} className="entity-tag">{id}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </section>

        {/* Event Log */}
        <section className="dashboard-panel events-panel">
          <div className="panel-header">
            <h2>Event Stream</h2>
            <span className="event-count">{recentEvents.length} events</span>
          </div>

          <div className="events-list">
            {recentEvents.length === 0 ? (
              <div className="empty-state">
                <span className="empty-state__icon">📡</span>
                <p>Waiting for events...</p>
              </div>
            ) : (
              recentEvents.map((event) => (
                <div 
                  key={event.id} 
                  className={`event-item ${event.isNew ? 'event-item--new' : ''}`}
                >
                  <span className="event-item__type">{event.type}</span>
                  <span className="event-item__time">
                    {formatTimestamp(event.timestamp)}
                  </span>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      {/* Detail Modal */}
      {selectedContradiction && (
        <div className="detail-overlay" onClick={() => setSelectedContradiction(null)}>
          <div className="detail-modal" onClick={(e) => e.stopPropagation()}>
            <button 
              className="detail-modal__close"
              onClick={() => setSelectedContradiction(null)}
            >
              ×
            </button>
            <div className="detail-modal__header">
              <span className={`severity-badge ${getSeverityClass(selectedContradiction.severity)}`}>
                {selectedContradiction.severity}
              </span>
              <h3>Contradiction #{selectedContradiction.contradiction_id}</h3>
            </div>
            <div className="detail-modal__content">
              <div className="detail-field">
                <label>Type</label>
                <span>{selectedContradiction.contradiction_type || 'Unknown'}</span>
              </div>
              <div className="detail-field">
                <label>Description</label>
                <p>{selectedContradiction.description}</p>
              </div>
              {selectedContradiction.entity_ids?.length > 0 && (
                <div className="detail-field">
                  <label>Affected Entities</label>
                  <div className="entity-list">
                    {selectedContradiction.entity_ids.map((id, i) => (
                      <span key={i} className="entity-tag entity-tag--large">{id}</span>
                    ))}
                  </div>
                </div>
              )}
              {selectedContradiction.evidence && (
                <div className="detail-field">
                  <label>Evidence</label>
                  <pre className="evidence-block">
                    {typeof selectedContradiction.evidence === 'string' 
                      ? selectedContradiction.evidence 
                      : JSON.stringify(selectedContradiction.evidence, null, 2)}
                  </pre>
                </div>
              )}
            </div>
            <div className="detail-modal__actions">
              <button className="btn btn--secondary">Dismiss</button>
              <button className="btn btn--primary">Resolve</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard


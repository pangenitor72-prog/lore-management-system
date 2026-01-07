import { useState, useEffect } from 'react'
import './Library.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const ENTITY_TYPES = [
  'ALL',
  'Character',
  'Location',
  'Faction',
  'Item',
  'Event',
  'Concept'
]

export default function Library() {
  const [entities, setEntities] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // Filters
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedEntity, setSelectedEntity] = useState(null)

  useEffect(() => {
    fetchEntities()
  }, [typeFilter])

  const fetchEntities = async () => {
    setLoading(true)
    setError(null)
    try {
      const url = new URL(`${window.location.origin}${API_BASE}/entities`)
      if (typeFilter !== 'ALL') {
        url.searchParams.append('entity_type', typeFilter)
      }
      
      const res = await fetch(url)
      if (!res.ok) throw new Error('Failed to fetch entities')
      
      const data = await res.json()
      setEntities(data)
    } catch (err) {
      console.error(err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const filteredEntities = entities.filter(e => 
    e.canonical_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (e.aliases || []).some(a => a.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  const handleCardClick = (entity) => {
    setSelectedEntity(entity)
  }

  const closeDetail = () => setSelectedEntity(null)

  return (
    <div className="library">
      <header className="library-header">
        <div className="library-header__title">
          <span className="library-header__icon">🏛️</span>
          <h1>Lore Library</h1>
        </div>
        <div className="library-header__controls">
          <div className="search-bar">
            <input 
              type="text" 
              placeholder="Search archives..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <select 
            value={typeFilter} 
            onChange={(e) => setTypeFilter(e.target.value)}
            className="filter-select"
          >
            {ENTITY_TYPES.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      </header>

      <div className="library-content">
        {loading ? (
          <div className="loading-state">
            <span className="loading-spinner"></span>
            <p>Retrieving records...</p>
          </div>
        ) : error ? (
          <div className="error-state">
            <p>Error: {error}</p>
            <button onClick={fetchEntities}>Retry</button>
          </div>
        ) : filteredEntities.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state__icon">🕸️</span>
            <p>No records found.</p>
          </div>
        ) : (
          <div className="entity-grid">
            {filteredEntities.map(entity => (
              <div 
                key={entity.canon_id} 
                className="entity-card"
                onClick={() => handleCardClick(entity)}
              >
                <div className="entity-card__header">
                  <span className={`type-badge type-badge--${entity.entity_type.toLowerCase()}`}>
                    {entity.entity_type}
                  </span>
                  {entity.confidence_level === 'AI_GENERATED' && (
                    <span className="ai-badge" title="AI Generated">🤖</span>
                  )}
                </div>
                <h3>{entity.canonical_name}</h3>
                {entity.approved_fields?.description ? (
                  <p className="entity-desc">{entity.approved_fields.description.substring(0, 100)}...</p>
                ) : (
                  <p className="entity-desc text-muted">No description available.</p>
                )}
                <div className="entity-card__footer">
                  <span className="entity-id">ID: {entity.canon_id.substring(0, 8)}...</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedEntity && (
        <div className="detail-overlay" onClick={closeDetail}>
          <div className="detail-modal" onClick={e => e.stopPropagation()}>
            <button className="detail-modal__close" onClick={closeDetail}>×</button>
            
            <header className="detail-modal__header">
              <span className={`type-badge type-badge--${selectedEntity.entity_type.toLowerCase()}`}>
                {selectedEntity.entity_type}
              </span>
              <h2>{selectedEntity.canonical_name}</h2>
            </header>

            <div className="detail-modal__content">
              {selectedEntity.approved_fields?.description && (
                <section className="detail-section">
                  <h4>Description</h4>
                  <p>{selectedEntity.approved_fields.description}</p>
                </section>
              )}

              {selectedEntity.aliases?.length > 0 && (
                <section className="detail-section">
                  <h4>Aliases</h4>
                  <div className="tag-list">
                    {selectedEntity.aliases.map(a => (
                      <span key={a} className="tag">{a}</span>
                    ))}
                  </div>
                </section>
              )}

              <section className="detail-section">
                <h4>Metadata</h4>
                <div className="metadata-grid">
                  <div className="meta-item">
                    <label>Canon ID</label>
                    <span>{selectedEntity.canon_id}</span>
                  </div>
                  <div className="meta-item">
                    <label>Status</label>
                    <span>{selectedEntity.approval_status}</span>
                  </div>
                  <div className="meta-item">
                    <label>Confidence</label>
                    <span>{selectedEntity.confidence_level}</span>
                  </div>
                  <div className="meta-item">
                    <label>Knowledge</label>
                    <span>{selectedEntity.party_knowledge || 'UNKNOWN'}</span>
                  </div>
                </div>
              </section>

              {/* Raw Properties Dump (for development/completeness) */}
              <section className="detail-section">
                <h4>Properties</h4>
                <pre className="raw-json">
                  {JSON.stringify(selectedEntity.approved_fields, null, 2)}
                </pre>
              </section>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

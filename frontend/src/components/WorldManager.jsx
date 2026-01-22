import { useState, useEffect } from 'react'
import './WorldManager.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const GENRES = [
  'fantasy', 'scifi', 'horror', 'western', 'noir', 'cyberpunk',
  'wuxia', 'superhero', 'steampunk', 'postapoc', 'pirate',
  'mythology', 'modern', 'dark_fantasy', 'space_opera'
]

const ENTITY_TYPES = [
  'character', 'location', 'faction', 'item', 'event', 'concept'
]

export default function WorldManager() {
  const [worlds, setWorlds] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [showEntitiesModal, setShowEntitiesModal] = useState(false)

  // Selected world for operations
  const [selectedWorld, setSelectedWorld] = useState(null)

  // Form state for create/edit
  const [formData, setFormData] = useState({
    id: '',
    name: '',
    description: '',
    genre: 'fantasy',
    genre_hints: [],
    tone_hints: [],
    seed_prompt: '',
    lore_content: '',
  })

  // Review state - entities extracted for human review
  const [reviewEntities, setReviewEntities] = useState([]) // [{...entity, selected: true, editing: false}]
  const [reviewLoading, setReviewLoading] = useState(false)
  const [typeFilter, setTypeFilter] = useState('all')

  // Entities state (for viewing existing world entities)
  const [entities, setEntities] = useState([])
  const [entitiesLoading, setEntitiesLoading] = useState(false)

  // Operation state
  const [operating, setOperating] = useState(false)

  useEffect(() => {
    fetchWorlds()
  }, [])

  const fetchWorlds = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/game/lore-bases`)
      if (!res.ok) throw new Error('Failed to fetch worlds')
      const data = await res.json()
      setWorlds(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const openCreateModal = () => {
    setFormData({
      id: '',
      name: '',
      description: '',
      genre: 'fantasy',
      genre_hints: ['fantasy'],
      tone_hints: [],
      seed_prompt: '',
      lore_content: '',
    })
    setReviewEntities([])
    setTypeFilter('all')
    setShowCreateModal(true)
  }

  const openEditModal = (world) => {
    setSelectedWorld(world)
    setReviewEntities([])
    setTypeFilter('all')
    // Fetch full world data including lore_content
    fetchWorldDetails(world.id)
    setShowEditModal(true)
  }

  const fetchWorldDetails = async (worldId) => {
    try {
      const res = await fetch(`${API_BASE}/game/lore-bases/${worldId}`)
      if (res.ok) {
        const data = await res.json()
        setFormData({
          id: data.id,
          name: data.name,
          description: data.description || '',
          genre: data.genre || 'fantasy',
          genre_hints: data.genre_hints || [],
          tone_hints: data.tone_hints || [],
          seed_prompt: data.seed_prompt || '',
          lore_content: '', // We'll need to fetch this separately or from a different endpoint
        })
      }
    } catch (err) {
      console.error('Failed to fetch world details:', err)
    }
  }

  const openDeleteModal = (world) => {
    setSelectedWorld(world)
    setShowDeleteModal(true)
  }

  const openPreviewModal = (world) => {
    setSelectedWorld(world)
    setPreviewData(null)
    setShowPreviewModal(true)
  }

  const openEntitiesModal = async (world) => {
    setSelectedWorld(world)
    setEntitiesLoading(true)
    setShowEntitiesModal(true)

    try {
      const res = await fetch(`${API_BASE}/game/lore-bases/${world.id}/entities`)
      if (res.ok) {
        const data = await res.json()
        setEntities(data.entities || [])
      }
    } catch (err) {
      console.error('Failed to fetch entities:', err)
    } finally {
      setEntitiesLoading(false)
    }
  }

  const handleCreateWorld = async () => {
    if (!formData.id || !formData.name || !formData.description) {
      alert('Please fill in ID, Name, and Description')
      return
    }

    // Get selected entities for creation
    const selectedEntities = reviewEntities
      .filter(e => e.selected)
      .map(({ selected, editing, id, ...entity }) => entity) // Remove UI state

    setOperating(true)
    try {
      const res = await fetch(`${API_BASE}/api/game/lore-bases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: formData.id.toLowerCase().replace(/\s+/g, '_'),
          name: formData.name,
          description: formData.description,
          genre_hints: formData.genre_hints.length ? formData.genre_hints : [formData.genre],
          tone_hints: formData.tone_hints,
          seed_prompt: formData.seed_prompt,
          lore_content: formData.lore_content,
          approved_entities: selectedEntities.length > 0 ? selectedEntities : undefined,
        }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to create world')
      }

      const result = await res.json()
      if (result.entities_created > 0) {
        alert(`Created ${formData.name} with ${result.entities_created} entities`)
      }

      await fetchWorlds()
      setShowCreateModal(false)
    } catch (err) {
      alert(`Error: ${err.message}`)
    } finally {
      setOperating(false)
    }
  }

  const handleUpdateWorld = async () => {
    if (!selectedWorld) return

    // Get selected entities for creation
    const selectedEntities = reviewEntities
      .filter(e => e.selected)
      .map(({ selected, editing, id, ...entity }) => entity) // Remove UI state

    setOperating(true)
    try {
      const res = await fetch(`${API_BASE}/game/lore-bases/${selectedWorld.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name || undefined,
          description: formData.description || undefined,
          genre: formData.genre || undefined,
          genre_hints: formData.genre_hints.length ? formData.genre_hints : undefined,
          tone_hints: formData.tone_hints.length ? formData.tone_hints : undefined,
          seed_prompt: formData.seed_prompt || undefined,
          lore_content: formData.lore_content || undefined,
          approved_entities: selectedEntities.length > 0 ? selectedEntities : undefined,
        }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to update world')
      }

      const result = await res.json()
      if (result.entities_created > 0) {
        alert(`Updated ${selectedWorld.name}: ${result.entities_created} new entities added`)
      }

      await fetchWorlds()
      setShowEditModal(false)
    } catch (err) {
      alert(`Error: ${err.message}`)
    } finally {
      setOperating(false)
    }
  }

  const handleDeleteWorld = async () => {
    if (!selectedWorld) return

    setOperating(true)
    try {
      const res = await fetch(`${API_BASE}/game/lore-bases/${selectedWorld.id}?delete_entities=true`, {
        method: 'DELETE',
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to delete world')
      }

      const result = await res.json()
      alert(`Deleted ${selectedWorld.name}: ${result.entities_deleted} entities removed`)

      await fetchWorlds()
      setShowDeleteModal(false)
    } catch (err) {
      alert(`Error: ${err.message}`)
    } finally {
      setOperating(false)
    }
  }

  const handlePreview = async () => {
    if (!formData.lore_content || formData.lore_content.length < 50) {
      alert('Please enter at least 50 characters of lore content to preview')
      return
    }

    setReviewLoading(true)
    setReviewEntities([])
    try {
      const worldId = selectedWorld?.id || formData.id || 'preview'
      const res = await fetch(`${API_BASE}/game/lore-bases/${worldId}/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lore_content: formData.lore_content }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Preview failed')
      }

      const data = await res.json()
      // Transform entities into review format with selection state
      const entitiesWithState = (data.entities || []).map((entity, index) => ({
        ...entity,
        id: index, // temporary id for UI
        selected: true,
        editing: false,
      }))
      setReviewEntities(entitiesWithState)
    } catch (err) {
      alert(`Preview error: ${err.message}`)
    } finally {
      setReviewLoading(false)
    }
  }

  // Review entity handlers
  const toggleEntitySelection = (index) => {
    setReviewEntities(prev => prev.map((e, i) =>
      i === index ? { ...e, selected: !e.selected } : e
    ))
  }

  const toggleAllEntities = (selected) => {
    setReviewEntities(prev => prev.map(e => {
      // Only toggle entities that match the current filter
      if (typeFilter === 'all' || e.type?.toLowerCase() === typeFilter) {
        return { ...e, selected }
      }
      return e
    }))
  }

  const toggleEntityEditing = (index) => {
    setReviewEntities(prev => prev.map((e, i) =>
      i === index ? { ...e, editing: !e.editing } : e
    ))
  }

  const updateEntity = (index, field, value) => {
    setReviewEntities(prev => prev.map((e, i) =>
      i === index ? { ...e, [field]: value } : e
    ))
  }

  const deleteEntity = (index) => {
    setReviewEntities(prev => prev.filter((_, i) => i !== index))
  }

  const getFilteredEntities = () => {
    if (typeFilter === 'all') return reviewEntities
    return reviewEntities.filter(e => e.type?.toLowerCase() === typeFilter)
  }

  const getSelectedCount = () => {
    return reviewEntities.filter(e => e.selected).length
  }

  const getTypeCounts = () => {
    const counts = {}
    reviewEntities.forEach(e => {
      const type = e.type?.toLowerCase() || 'unknown'
      counts[type] = (counts[type] || 0) + 1
    })
    return counts
  }

  const handleIngest = async () => {
    if (!selectedWorld) return

    setOperating(true)
    try {
      const res = await fetch(`${API_BASE}/game/lore-bases/${selectedWorld.id}/ingest`, {
        method: 'POST',
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Ingest failed')
      }

      const result = await res.json()
      alert(`Ingested: ${result.entities_created} entities, ${result.npcs_with_ocean} with personalities`)

      await fetchWorlds()
    } catch (err) {
      alert(`Ingest error: ${err.message}`)
    } finally {
      setOperating(false)
    }
  }

  const handleGenreChange = (genre) => {
    setFormData(prev => ({
      ...prev,
      genre,
      genre_hints: prev.genre_hints.includes(genre)
        ? prev.genre_hints
        : [genre, ...prev.genre_hints.filter(g => g !== genre)]
    }))
  }

  // Drag and drop state
  const [isDragging, setIsDragging] = useState(false)

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const readFileContent = async (file) => {
    const validExtensions = ['.txt', '.md', '.json']
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()

    if (!validExtensions.includes(ext)) {
      throw new Error(`Unsupported file type: ${ext}\nSupported: .txt, .md, .json`)
    }

    const text = await file.text()

    // If it's JSON, try to extract lore_content or just use the whole thing
    if (ext === '.json') {
      try {
        const json = JSON.parse(text)
        return json.lore_content || json.content || json.text || JSON.stringify(json, null, 2)
      } catch {
        return text
      }
    }

    return text
  }

  const appendLoreContent = (content) => {
    setFormData(prev => ({
      ...prev,
      lore_content: prev.lore_content
        ? prev.lore_content + '\n\n' + content
        : content
    }))
  }

  const handleDrop = async (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = Array.from(e.dataTransfer.files)
    if (files.length === 0) return

    try {
      for (const file of files) {
        const content = await readFileContent(file)
        appendLoreContent(content)
      }
    } catch (err) {
      alert(err.message)
    }
  }

  const handlePaste = async (e) => {
    const items = e.clipboardData?.items
    if (!items) return

    for (const item of items) {
      // Check if it's a file
      if (item.kind === 'file') {
        e.preventDefault()
        const file = item.getAsFile()
        if (file) {
          try {
            const content = await readFileContent(file)
            appendLoreContent(content)
          } catch (err) {
            alert(err.message)
          }
        }
        return
      }
    }
    // If not a file, let default paste behavior handle it (text)
  }

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files)
    if (files.length === 0) return

    try {
      for (const file of files) {
        const content = await readFileContent(file)
        appendLoreContent(content)
      }
    } catch (err) {
      alert(err.message)
    }

    // Reset input so same file can be selected again
    e.target.value = ''
  }

  return (
    <div className="world-manager">
      <header className="world-manager-header">
        <div className="world-manager-header__title">
          <span className="world-manager-header__icon">🌍</span>
          <h1>World Manager</h1>
        </div>
        <button className="btn btn--primary" onClick={openCreateModal}>
          + Create World
        </button>
      </header>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={fetchWorlds}>Retry</button>
        </div>
      )}

      <div className="worlds-grid">
        {loading ? (
          <div className="loading-state">
            <span className="loading-spinner"></span>
            <p>Loading worlds...</p>
          </div>
        ) : worlds.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state__icon">🌌</span>
            <p>No worlds yet</p>
            <button className="btn btn--primary" onClick={openCreateModal}>
              Create Your First World
            </button>
          </div>
        ) : (
          worlds.map(world => (
            <div key={world.id} className="world-card">
              <div className="world-card__header">
                <span className={`genre-badge genre-badge--${world.genre || 'fantasy'}`}>
                  {world.genre || 'fantasy'}
                </span>
                {world.is_seed && <span className="seed-badge">Seed</span>}
                {world.ingested && <span className="ingested-badge">Ingested</span>}
              </div>

              <h3 className="world-card__name">{world.name}</h3>
              <p className="world-card__description">{world.description}</p>

              <div className="world-card__stats">
                <div className="stat">
                  <span className="stat__value">{world.entities_count || 0}</span>
                  <span className="stat__label">Entities</span>
                </div>
                <div className="stat">
                  <span className="stat__value">{world.has_lore_content ? 'Yes' : 'No'}</span>
                  <span className="stat__label">Has Lore</span>
                </div>
              </div>

              <div className="world-card__actions">
                <button
                  className="btn btn--small"
                  onClick={() => openEntitiesModal(world)}
                  disabled={world.entities_count === 0}
                >
                  View Entities
                </button>
                <button
                  className="btn btn--small"
                  onClick={() => openEditModal(world)}
                >
                  Edit
                </button>
                <button
                  className="btn btn--small btn--danger"
                  onClick={() => openDeleteModal(world)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Create World Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal modal--large" onClick={e => e.stopPropagation()}>
            <button className="modal__close" onClick={() => setShowCreateModal(false)}>x</button>
            <h2>Create New World</h2>

            <div className="form-grid">
              <div className="form-group">
                <label>World ID (lowercase, no spaces)</label>
                <input
                  type="text"
                  value={formData.id}
                  onChange={e => setFormData(prev => ({ ...prev, id: e.target.value.toLowerCase().replace(/\s+/g, '_') }))}
                  placeholder="my_world"
                />
              </div>

              <div className="form-group">
                <label>World Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="My Amazing World"
                />
              </div>

              <div className="form-group form-group--full">
                <label>Description</label>
                <textarea
                  value={formData.description}
                  onChange={e => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="A brief description of your world..."
                  rows={3}
                />
              </div>

              <div className="form-group">
                <label>Primary Genre</label>
                <select
                  value={formData.genre}
                  onChange={e => handleGenreChange(e.target.value)}
                >
                  {GENRES.map(g => (
                    <option key={g} value={g}>{g.replace('_', ' ').toUpperCase()}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Seed Prompt (for AI generation)</label>
                <input
                  type="text"
                  value={formData.seed_prompt}
                  onChange={e => setFormData(prev => ({ ...prev, seed_prompt: e.target.value }))}
                  placeholder="A dark fantasy realm where..."
                />
              </div>

              <div className="form-group form-group--full">
                <label>Lore Content</label>
                <div
                  className={`drop-zone ${isDragging ? 'drop-zone--active' : ''}`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  <textarea
                    value={formData.lore_content}
                    onChange={e => setFormData(prev => ({ ...prev, lore_content: e.target.value }))}
                    onPaste={handlePaste}
                    placeholder="Type, paste, or drag files here (.txt, .md, .json)&#10;&#10;Add your world's lore, NPCs, locations, factions...&#10;The AI will extract entities from this text."
                    rows={12}
                  />
                  {isDragging && (
                    <div className="drop-zone__overlay">
                      <span>Drop file to add lore</span>
                    </div>
                  )}
                </div>
                <div className="form-hint">
                  <span>{formData.lore_content.length} characters</span>
                  <div className="form-hint__actions">
                    <label className="btn btn--small btn--secondary file-input-label">
                      Browse Files
                      <input
                        type="file"
                        accept=".txt,.md,.json"
                        onChange={handleFileSelect}
                        style={{ display: 'none' }}
                      />
                    </label>
                    {formData.lore_content.length >= 50 && (
                      <button
                        className="btn btn--small btn--primary"
                        onClick={handlePreview}
                        disabled={reviewLoading}
                      >
                        {reviewLoading ? 'Analyzing...' : 'Extract & Review'}
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Entity Review Step */}
              {reviewEntities.length > 0 && (
                <div className="form-group form-group--full review-step">
                  <div className="review-header">
                    <h4>Review Extracted Entities ({reviewEntities.length} found)</h4>
                    <div className="review-controls">
                      <button
                        className="btn btn--small btn--secondary"
                        onClick={() => toggleAllEntities(true)}
                      >
                        Select All
                      </button>
                      <button
                        className="btn btn--small btn--secondary"
                        onClick={() => toggleAllEntities(false)}
                      >
                        Deselect All
                      </button>
                      <select
                        className="type-filter"
                        value={typeFilter}
                        onChange={e => setTypeFilter(e.target.value)}
                      >
                        <option value="all">All Types ({reviewEntities.length})</option>
                        {Object.entries(getTypeCounts()).map(([type, count]) => (
                          <option key={type} value={type}>
                            {type.charAt(0).toUpperCase() + type.slice(1)} ({count})
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="review-list">
                    {getFilteredEntities().map((entity, displayIndex) => {
                      const actualIndex = reviewEntities.findIndex(e => e === entity)
                      return (
                        <div
                          key={actualIndex}
                          className={`review-entity ${entity.selected ? 'review-entity--selected' : 'review-entity--deselected'}`}
                        >
                          <div className="review-entity__main">
                            <input
                              type="checkbox"
                              checked={entity.selected}
                              onChange={() => toggleEntitySelection(actualIndex)}
                              className="review-entity__checkbox"
                            />

                            {entity.editing ? (
                              <div className="review-entity__edit-form">
                                <select
                                  value={entity.type?.toLowerCase() || 'character'}
                                  onChange={e => updateEntity(actualIndex, 'type', e.target.value)}
                                  className="type-select"
                                >
                                  {ENTITY_TYPES.map(t => (
                                    <option key={t} value={t}>{t.toUpperCase()}</option>
                                  ))}
                                </select>
                                <input
                                  type="text"
                                  value={entity.name || ''}
                                  onChange={e => updateEntity(actualIndex, 'name', e.target.value)}
                                  placeholder="Entity name"
                                  className="name-input"
                                />
                                <textarea
                                  value={entity.description || ''}
                                  onChange={e => updateEntity(actualIndex, 'description', e.target.value)}
                                  placeholder="Description"
                                  rows={2}
                                  className="desc-input"
                                />
                                <div className="edit-actions">
                                  <button
                                    className="btn btn--small btn--primary"
                                    onClick={() => toggleEntityEditing(actualIndex)}
                                  >
                                    Done
                                  </button>
                                  <button
                                    className="btn btn--small btn--danger"
                                    onClick={() => deleteEntity(actualIndex)}
                                  >
                                    Delete
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <>
                                <span className={`type-tag type-tag--${entity.type?.toLowerCase() || 'character'}`}>
                                  {entity.type || 'CHARACTER'}
                                </span>
                                <span className="review-entity__name">{entity.name}</span>
                                <span className="review-entity__desc">
                                  {entity.description?.substring(0, 80)}
                                  {entity.description?.length > 80 ? '...' : ''}
                                </span>
                                <button
                                  className="btn btn--small btn--secondary review-entity__edit-btn"
                                  onClick={() => toggleEntityEditing(actualIndex)}
                                >
                                  Edit
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  <div className="review-summary">
                    <span className="review-summary__count">
                      {getSelectedCount()} of {reviewEntities.length} entities selected
                    </span>
                  </div>
                </div>
              )}
            </div>

            <div className="modal__actions">
              <button className="btn btn--secondary" onClick={() => setShowCreateModal(false)}>
                Cancel
              </button>
              <button
                className="btn btn--primary"
                onClick={handleCreateWorld}
                disabled={operating}
              >
                {operating ? 'Creating...' : 'Create World'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit World Modal */}
      {showEditModal && selectedWorld && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal modal--large" onClick={e => e.stopPropagation()}>
            <button className="modal__close" onClick={() => setShowEditModal(false)}>x</button>
            <h2>Edit: {selectedWorld.name}</h2>

            <div className="form-grid">
              <div className="form-group">
                <label>World Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={e => setFormData(prev => ({ ...prev, name: e.target.value }))}
                />
              </div>

              <div className="form-group">
                <label>Primary Genre</label>
                <select
                  value={formData.genre}
                  onChange={e => handleGenreChange(e.target.value)}
                >
                  {GENRES.map(g => (
                    <option key={g} value={g}>{g.replace('_', ' ').toUpperCase()}</option>
                  ))}
                </select>
              </div>

              <div className="form-group form-group--full">
                <label>Description</label>
                <textarea
                  value={formData.description}
                  onChange={e => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  rows={3}
                />
              </div>

              <div className="form-group form-group--full">
                <label>Add More Lore Content</label>
                <div
                  className={`drop-zone ${isDragging ? 'drop-zone--active' : ''}`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  <textarea
                    value={formData.lore_content}
                    onChange={e => setFormData(prev => ({ ...prev, lore_content: e.target.value }))}
                    onPaste={handlePaste}
                    placeholder="Type, paste, or drag files here (.txt, .md, .json)&#10;&#10;Add additional lore to be extracted..."
                    rows={8}
                  />
                  {isDragging && (
                    <div className="drop-zone__overlay">
                      <span>Drop file to add lore</span>
                    </div>
                  )}
                </div>
                <div className="form-hint">
                  <span>{formData.lore_content.length} characters</span>
                  <div className="form-hint__actions">
                    <label className="btn btn--small btn--secondary file-input-label">
                      Browse Files
                      <input
                        type="file"
                        accept=".txt,.md,.json"
                        onChange={handleFileSelect}
                        style={{ display: 'none' }}
                      />
                    </label>
                    {formData.lore_content.length >= 50 && (
                      <button
                        className="btn btn--small btn--primary"
                        onClick={handlePreview}
                        disabled={reviewLoading}
                      >
                        {reviewLoading ? 'Analyzing...' : 'Extract & Review'}
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Entity Review Step */}
              {reviewEntities.length > 0 && (
                <div className="form-group form-group--full review-step">
                  <div className="review-header">
                    <h4>Review New Entities ({reviewEntities.length} found)</h4>
                    <div className="review-controls">
                      <button
                        className="btn btn--small btn--secondary"
                        onClick={() => toggleAllEntities(true)}
                      >
                        Select All
                      </button>
                      <button
                        className="btn btn--small btn--secondary"
                        onClick={() => toggleAllEntities(false)}
                      >
                        Deselect All
                      </button>
                      <select
                        className="type-filter"
                        value={typeFilter}
                        onChange={e => setTypeFilter(e.target.value)}
                      >
                        <option value="all">All Types ({reviewEntities.length})</option>
                        {Object.entries(getTypeCounts()).map(([type, count]) => (
                          <option key={type} value={type}>
                            {type.charAt(0).toUpperCase() + type.slice(1)} ({count})
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="review-list">
                    {getFilteredEntities().map((entity, displayIndex) => {
                      const actualIndex = reviewEntities.findIndex(e => e === entity)
                      return (
                        <div
                          key={actualIndex}
                          className={`review-entity ${entity.selected ? 'review-entity--selected' : 'review-entity--deselected'}`}
                        >
                          <div className="review-entity__main">
                            <input
                              type="checkbox"
                              checked={entity.selected}
                              onChange={() => toggleEntitySelection(actualIndex)}
                              className="review-entity__checkbox"
                            />

                            {entity.editing ? (
                              <div className="review-entity__edit-form">
                                <select
                                  value={entity.type?.toLowerCase() || 'character'}
                                  onChange={e => updateEntity(actualIndex, 'type', e.target.value)}
                                  className="type-select"
                                >
                                  {ENTITY_TYPES.map(t => (
                                    <option key={t} value={t}>{t.toUpperCase()}</option>
                                  ))}
                                </select>
                                <input
                                  type="text"
                                  value={entity.name || ''}
                                  onChange={e => updateEntity(actualIndex, 'name', e.target.value)}
                                  placeholder="Entity name"
                                  className="name-input"
                                />
                                <textarea
                                  value={entity.description || ''}
                                  onChange={e => updateEntity(actualIndex, 'description', e.target.value)}
                                  placeholder="Description"
                                  rows={2}
                                  className="desc-input"
                                />
                                <div className="edit-actions">
                                  <button
                                    className="btn btn--small btn--primary"
                                    onClick={() => toggleEntityEditing(actualIndex)}
                                  >
                                    Done
                                  </button>
                                  <button
                                    className="btn btn--small btn--danger"
                                    onClick={() => deleteEntity(actualIndex)}
                                  >
                                    Delete
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <>
                                <span className={`type-tag type-tag--${entity.type?.toLowerCase() || 'character'}`}>
                                  {entity.type || 'CHARACTER'}
                                </span>
                                <span className="review-entity__name">{entity.name}</span>
                                <span className="review-entity__desc">
                                  {entity.description?.substring(0, 80)}
                                  {entity.description?.length > 80 ? '...' : ''}
                                </span>
                                <button
                                  className="btn btn--small btn--secondary review-entity__edit-btn"
                                  onClick={() => toggleEntityEditing(actualIndex)}
                                >
                                  Edit
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  <div className="review-summary">
                    <span className="review-summary__count">
                      {getSelectedCount()} of {reviewEntities.length} entities selected
                    </span>
                  </div>
                </div>
              )}

              {!selectedWorld.ingested && selectedWorld.has_lore_content && reviewEntities.length === 0 && (
                <div className="form-group form-group--full">
                  <div className="ingest-prompt">
                    <p>This world has lore content that hasn't been processed yet.</p>
                    <button
                      className="btn btn--primary"
                      onClick={handleIngest}
                      disabled={operating}
                    >
                      {operating ? 'Processing...' : 'Extract Entities Now'}
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="modal__actions">
              <button className="btn btn--secondary" onClick={() => setShowEditModal(false)}>
                Cancel
              </button>
              <button
                className="btn btn--primary"
                onClick={handleUpdateWorld}
                disabled={operating}
              >
                {operating ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && selectedWorld && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal modal--danger" onClick={e => e.stopPropagation()}>
            <h2>Delete World?</h2>
            <p>
              Are you sure you want to delete <strong>{selectedWorld.name}</strong>?
            </p>
            <p className="warning-text">
              This will also delete all {selectedWorld.entities_count || 0} entities belonging to this world.
              This action cannot be undone.
            </p>

            <div className="modal__actions">
              <button className="btn btn--secondary" onClick={() => setShowDeleteModal(false)}>
                Cancel
              </button>
              <button
                className="btn btn--danger"
                onClick={handleDeleteWorld}
                disabled={operating}
              >
                {operating ? 'Deleting...' : 'Delete World'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Entities Modal */}
      {showEntitiesModal && selectedWorld && (
        <div className="modal-overlay" onClick={() => setShowEntitiesModal(false)}>
          <div className="modal modal--large" onClick={e => e.stopPropagation()}>
            <button className="modal__close" onClick={() => setShowEntitiesModal(false)}>x</button>
            <h2>Entities in {selectedWorld.name}</h2>

            {entitiesLoading ? (
              <div className="loading-state">
                <span className="loading-spinner"></span>
                <p>Loading entities...</p>
              </div>
            ) : entities.length === 0 ? (
              <div className="empty-state">
                <p>No entities found for this world.</p>
              </div>
            ) : (
              <div className="entities-list">
                {entities.map(entity => (
                  <div key={entity.id} className="entity-row">
                    <span className={`type-tag type-tag--${entity.type?.toLowerCase()}`}>
                      {entity.type}
                    </span>
                    <span className="entity-name">{entity.name}</span>
                    <span className="entity-desc">{entity.description}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="modal__actions">
              <button className="btn btn--secondary" onClick={() => setShowEntitiesModal(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

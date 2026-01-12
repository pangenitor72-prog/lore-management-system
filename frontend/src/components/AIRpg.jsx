import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './AIRpg.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export default function AIRpg() {
  const navigate = useNavigate()
  const [saves, setSaves] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchSessions()
  }, [])

  const fetchSessions = async () => {
    try {
      // Using analytics endpoint as a proxy for session listing in this alpha
      const res = await fetch(`${API_BASE}/game/analytics`)
      if (res.ok) {
        const data = await res.json()
        // Map recent sessions to our save slot format
        const recent = data.recent_sessions || []
        const mappedSaves = recent.slice(0, 3).map((s, i) => ({
          id: s.session_id,
          name: `${s.character} in ${s.world}`,
          date: new Date(s.last_activity).toLocaleString(),
          level: s.turn_count, // Use turn count as a proxy for progress
          location: s.genre,   // Use genre as proxy for location/theme
          isReal: true
        }))
        
        // Pad with empty slots up to 3
        while (mappedSaves.length < 3) {
          mappedSaves.push({ 
            id: `empty-${mappedSaves.length}`, 
            name: "Empty Slot", 
            date: null, 
            level: null, 
            location: null,
            isReal: false
          })
        }
        setSaves(mappedSaves)
      }
    } catch (e) {
      console.error("Failed to fetch sessions", e)
      // Fallback to empty slots
      setSaves([
        { id: 'e1', name: "Empty Slot", date: null, level: null, location: null, isReal: false },
        { id: 'e2', name: "Empty Slot", date: null, level: null, location: null, isReal: false },
        { id: 'e3', name: "Empty Slot", date: null, level: null, location: null, isReal: false }
      ])
    } finally {
      setLoading(false)
    }
  }

  const handlePlay = (sessionId) => {
    // Navigate to chat interface with session ID
    navigate('/', { state: { sessionId } })
  }

  const handleDelete = async (slotId, e) => {
    e.stopPropagation()
    if (confirm("Are you sure you want to delete this save? (Admin only)")) {
      // TODO: Implement delete endpoint
      alert("Delete not implemented yet")
    }
  }

  const handleNewGame = async () => {
    const genre = prompt("Enter genre (fantasy, sci-fi, horror):", "fantasy")
    if (!genre) return

    try {
      const res = await fetch(`${API_BASE}/game/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          genre: genre,
          storytelling_style: "guided"
        })
      })
      
      if (res.ok) {
        const session = await res.json()
        navigate('/', { state: { sessionId: session.session_id } })
      }
    } catch (e) {
      alert("Failed to create new game: " + e.message)
    }
  }

  return (
    <div className="airpg-container">
      <header className="airpg-header">
        <h1>
          <span>🎲</span> AIRpg Play Mode
        </h1>
        <p>Select a campaign slot to continue your adventure.</p>
      </header>

      {loading ? (
        <div className="loading-state">Loading campaigns...</div>
      ) : (
        <div className="save-slots">
          {saves.map((slot, idx) => (
            <div 
              key={slot.id} 
              className={`save-slot ${!slot.isReal ? 'save-slot--empty' : ''}`}
              onClick={() => slot.isReal ? handlePlay(slot.id) : handleNewGame()}
            >
              <div className="slot-header">
                <span className="slot-number">Slot {idx + 1}</span>
                {slot.isReal && <span className="status-dot status-dot--connected"></span>}
              </div>

              {slot.isReal ? (
                <>
                  <div className="slot-info">
                    <h3>{slot.name}</h3>
                  </div>
                  <div className="slot-meta">
                    <span>Turn {slot.level}</span>
                    <span>📍 {slot.location}</span>
                    <span>🕒 {slot.date}</span>
                  </div>
                  <div className="slot-actions">
                    <button className="btn-play" onClick={(e) => {
                      e.stopPropagation()
                      handlePlay(slot.id)
                    }}>
                      Continue
                    </button>
                    {/* Admin delete only for now */}
                  </div>
                </>
              ) : (
                <>
                  <div className="new-game-plus">+</div>
                  <span className="empty-text">New Game</span>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


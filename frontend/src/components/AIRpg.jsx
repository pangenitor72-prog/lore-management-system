import { useState } from 'react'
import './AIRpg.css'

export default function AIRpg() {
  // Mock save data for now
  const [saves, setSaves] = useState([
    { id: 1, name: "Campaign of the Black Sun", date: "2025-11-28 14:30", level: 5, location: "Ruins of Xarth" },
    { id: 2, name: "Empty Slot", date: null, level: null, location: null },
    { id: 3, name: "Empty Slot", date: null, level: null, location: null }
  ])

  const handlePlay = (slotId) => {
    console.log(`Loading save slot ${slotId}`)
    // TODO: Connect to actual game session API
  }

  const handleDelete = (slotId, e) => {
    e.stopPropagation()
    if (confirm("Are you sure you want to delete this save?")) {
      setSaves(prev => prev.map(slot => 
        slot.id === slotId 
          ? { ...slot, name: "Empty Slot", date: null, level: null, location: null }
          : slot
      ))
    }
  }

  const handleNewGame = (slotId) => {
    console.log(`Creating new game in slot ${slotId}`)
    // TODO: Show new game modal
  }

  return (
    <div className="airpg-container">
      <header className="airpg-header">
        <h1>
          <span>🎲</span> AIRpg Play Mode
        </h1>
        <p>Select a campaign slot to continue your adventure.</p>
      </header>

      <div className="save-slots">
        {saves.map(slot => (
          <div 
            key={slot.id} 
            className={`save-slot ${!slot.date ? 'save-slot--empty' : ''}`}
            onClick={() => slot.date ? handlePlay(slot.id) : handleNewGame(slot.id)}
          >
            <div className="slot-header">
              <span className="slot-number">Slot {slot.id}</span>
              {slot.date && <span className="status-dot status-dot--connected"></span>}
            </div>

            {slot.date ? (
              <>
                <div className="slot-info">
                  <h3>{slot.name}</h3>
                </div>
                <div className="slot-meta">
                  <span>Level {slot.level} Party</span>
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
                  <button className="btn-delete" onClick={(e) => handleDelete(slot.id, e)}>
                    🗑️
                  </button>
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
    </div>
  )
}


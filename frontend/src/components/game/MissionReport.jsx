import { useEffect } from 'react'
import './MissionReport.css'

/**
 * MissionReport Component - The End Screen
 *
 * Displays when the game session ends (ONE_SHOT conclusion).
 *
 * Props:
 *   isOpen: boolean
 *   sessionData: { session_id, turns, itemsCollected, gold, ... }
 *   onReturnToMenu: () => void
 *   onSaveToChronicles: () => void
 */
export function MissionReport({
  isOpen,
  sessionData = {},
  onReturnToMenu,
  onSaveToChronicles
}) {
  // Prevent scrolling when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  if (!isOpen) return null

  const {
    turns = 0,
    itemsCollected = [],
    goldEarned = 0,
    skillChecks = { successes: 0, failures: 0 },
    combats = { won: 0, fled: 0 },
    locationsVisited = [],
    finalNarrative = ''
  } = sessionData

  return (
    <div className="mission-report-overlay">
      <div className="mission-report">
        {/* Header */}
        <div className="mission-report__header">
          <div className="mission-report__title-group">
            <span className="mission-report__emblem">📜</span>
            <h1 className="mission-report__title">THE END</h1>
          </div>
          <p className="mission-report__subtitle">Your story has concluded</p>
        </div>

        {/* Content */}
        <div className="mission-report__content">
          {/* Final Narrative Summary */}
          {finalNarrative && (
            <div className="mission-report__narrative">
              <p>{finalNarrative}</p>
            </div>
          )}

          {/* Statistics Grid */}
          <div className="mission-report__stats">
            <h3>Session Statistics</h3>
            <div className="stats-grid">
              <div className="stat-tile">
                <span className="stat-tile__icon">📖</span>
                <span className="stat-tile__value">{turns}</span>
                <span className="stat-tile__label">Turns</span>
              </div>

              <div className="stat-tile">
                <span className="stat-tile__icon">🪙</span>
                <span className="stat-tile__value">{goldEarned}</span>
                <span className="stat-tile__label">Gold Earned</span>
              </div>

              <div className="stat-tile">
                <span className="stat-tile__icon">📦</span>
                <span className="stat-tile__value">{itemsCollected.length}</span>
                <span className="stat-tile__label">Items Found</span>
              </div>

              <div className="stat-tile">
                <span className="stat-tile__icon">🎲</span>
                <span className="stat-tile__value">
                  {skillChecks.successes}/{skillChecks.successes + skillChecks.failures}
                </span>
                <span className="stat-tile__label">Checks Passed</span>
              </div>

              {combats.won + combats.fled > 0 && (
                <div className="stat-tile">
                  <span className="stat-tile__icon">⚔️</span>
                  <span className="stat-tile__value">{combats.won}</span>
                  <span className="stat-tile__label">Battles Won</span>
                </div>
              )}

              {locationsVisited.length > 0 && (
                <div className="stat-tile">
                  <span className="stat-tile__icon">📍</span>
                  <span className="stat-tile__value">{locationsVisited.length}</span>
                  <span className="stat-tile__label">Places Explored</span>
                </div>
              )}
            </div>
          </div>

          {/* Items Collected */}
          {itemsCollected.length > 0 && (
            <div className="mission-report__items">
              <h3>Treasures Collected</h3>
              <div className="items-list">
                {itemsCollected.map((item, index) => (
                  <div key={index} className="item-badge">
                    <span className="item-badge__icon">
                      {getItemIcon(item.type || item.item_type)}
                    </span>
                    <span className="item-badge__name">{item.name}</span>
                    {item.quantity > 1 && (
                      <span className="item-badge__qty">×{item.quantity}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="mission-report__actions">
          <button
            className="mission-report__btn mission-report__btn--secondary"
            onClick={onReturnToMenu}
          >
            Return to Menu
          </button>
          <button
            className="mission-report__btn mission-report__btn--primary"
            onClick={onSaveToChronicles}
          >
            <span className="btn-icon">📚</span>
            Save to Chronicles
          </button>
        </div>
      </div>
    </div>
  )
}

function getItemIcon(type) {
  const icons = {
    weapon: '⚔️',
    armor: '🛡️',
    consumable: '🧪',
    quest: '📜',
    misc: '📦'
  }
  return icons[type] || '📦'
}

export default MissionReport

import { useState, useEffect } from 'react'
import './InventoryDrawer.css'

/**
 * InventoryDrawer Component - The "Tactical" Layer
 *
 * Right-side drawer showing inventory and character stats.
 *
 * Props:
 *   isOpen: boolean
 *   onClose: () => void
 *   inventory: { items: Item[], gold: number }
 *   character: CharacterSheet | null
 *   mode: "STORY" | "RPG"
 *   hasNewItems: boolean - Triggers animation on backpack button
 */
export function InventoryDrawer({
  isOpen,
  onClose,
  inventory = { items: [], gold: 0 },
  character = null,
  mode = "STORY"
}) {
  const [activeTab, setActiveTab] = useState('inventory')

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  const showStats = mode === "RPG" && character

  // Group items by type
  const groupedItems = inventory.items?.reduce((acc, item) => {
    const type = item.type || item.item_type || 'misc'
    if (!acc[type]) acc[type] = []
    acc[type].push(item)
    return acc
  }, {}) || {}

  const itemTypeIcons = {
    weapon: '⚔️',
    armor: '🛡️',
    consumable: '🧪',
    quest: '📜',
    misc: '📦'
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className={`drawer-backdrop ${isOpen ? 'drawer-backdrop--visible' : ''}`}
        onClick={onClose}
      />

      {/* Drawer */}
      <div className={`inventory-drawer ${isOpen ? 'inventory-drawer--open' : ''}`}>
        {/* Header */}
        <div className="drawer-header">
          <h2>
            <span className="drawer-header__icon">🎒</span>
            Inventory
          </h2>
          <button className="drawer-close" onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Tabs (only show if RPG mode) */}
        {showStats && (
          <div className="drawer-tabs">
            <button
              className={`drawer-tab ${activeTab === 'inventory' ? 'drawer-tab--active' : ''}`}
              onClick={() => setActiveTab('inventory')}
            >
              Items
            </button>
            <button
              className={`drawer-tab ${activeTab === 'stats' ? 'drawer-tab--active' : ''}`}
              onClick={() => setActiveTab('stats')}
            >
              Character
            </button>
          </div>
        )}

        {/* Content */}
        <div className="drawer-content">
          {activeTab === 'inventory' && (
            <div className="inventory-panel">
              {/* Gold */}
              <div className="gold-display">
                <span className="gold-icon">🪙</span>
                <span className="gold-amount">{inventory.gold || 0}</span>
                <span className="gold-label">Gold</span>
              </div>

              {/* Item Grid */}
              {Object.keys(groupedItems).length > 0 ? (
                Object.entries(groupedItems).map(([type, items]) => (
                  <div key={type} className="item-category">
                    <h3 className="item-category__title">
                      <span>{itemTypeIcons[type] || '📦'}</span>
                      {type.charAt(0).toUpperCase() + type.slice(1)}
                    </h3>
                    <div className="item-grid">
                      {items.map((item, index) => (
                        <div
                          key={`${item.name}-${index}`}
                          className={`item-card ${item.equipped ? 'item-card--equipped' : ''}`}
                          title={item.description || item.name}
                        >
                          <div className="item-card__icon">
                            {getItemIcon(item)}
                          </div>
                          <div className="item-card__info">
                            <span className="item-card__name">{item.name}</span>
                            {item.quantity > 1 && (
                              <span className="item-card__qty">×{item.quantity}</span>
                            )}
                          </div>
                          {item.equipped && (
                            <span className="item-card__equipped">E</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="inventory-empty">
                  <span className="inventory-empty__icon">🎒</span>
                  <p>Your pack is empty</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'stats' && showStats && (
            <div className="stats-panel">
              {/* Character Header */}
              <div className="character-header">
                <div className="character-portrait">
                  {getClassIcon(character.archetype)}
                </div>
                <div className="character-info">
                  <h3 className="character-name">{character.name}</h3>
                  <span className="character-class">
                    {character.origin} {character.archetype}
                  </span>
                </div>
              </div>

              {/* Vital Stats */}
              <div className="vital-stats">
                <div className="stat-block stat-block--hp">
                  <span className="stat-label">HP</span>
                  <div className="stat-bar">
                    <div
                      className="stat-bar__fill"
                      style={{
                        width: `${(character.current_hit_points / character.max_hit_points) * 100}%`
                      }}
                    />
                  </div>
                  <span className="stat-value">
                    {character.current_hit_points} / {character.max_hit_points}
                  </span>
                </div>

                <div className="stat-row">
                  <div className="stat-block stat-block--compact">
                    <span className="stat-label">AC</span>
                    <span className="stat-value stat-value--large">
                      {character.armor_class || 10}
                    </span>
                  </div>
                  <div className="stat-block stat-block--compact">
                    <span className="stat-label">Level</span>
                    <span className="stat-value stat-value--large">
                      {character.level || 1}
                    </span>
                  </div>
                  <div className="stat-block stat-block--compact">
                    <span className="stat-label">Prof</span>
                    <span className="stat-value stat-value--large">
                      +{character.proficiency_bonus || 2}
                    </span>
                  </div>
                </div>
              </div>

              {/* Ability Scores */}
              {character.ability_scores && (
                <div className="ability-scores">
                  <h4>Abilities</h4>
                  <div className="abilities-grid">
                    {Object.entries(character.ability_scores).map(([ability, score]) => (
                      <div key={ability} className="ability-block">
                        <span className="ability-name">
                          {ability.slice(0, 3).toUpperCase()}
                        </span>
                        <span className="ability-score">{score}</span>
                        <span className="ability-mod">
                          {getModifier(score) >= 0 ? '+' : ''}{getModifier(score)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}

// Helper functions
function getModifier(score) {
  return Math.floor((score - 10) / 2)
}

function getItemIcon(item) {
  const type = item.type || item.item_type || 'misc'
  switch (type) {
    case 'weapon': return item.damage ? '⚔️' : '🗡️'
    case 'armor': return '🛡️'
    case 'consumable': return '🧪'
    case 'quest': return '📜'
    default: return '📦'
  }
}

function getClassIcon(archetype) {
  const icons = {
    fighter: '⚔️',
    wizard: '🧙',
    rogue: '🗡️',
    cleric: '✝️',
    ranger: '🏹',
    paladin: '🛡️',
    barbarian: '💪',
    bard: '🎵',
    druid: '🌿',
    monk: '👊',
    sorcerer: '✨',
    warlock: '👁️'
  }
  return icons[archetype?.toLowerCase()] || '🧑'
}

/**
 * BackpackButton - Trigger for the inventory drawer
 */
export function BackpackButton({ onClick, hasNewItems = false, itemCount = 0 }) {
  return (
    <button
      className={`backpack-button ${hasNewItems ? 'backpack-button--pulse' : ''}`}
      onClick={onClick}
      title="Open Inventory"
    >
      <span className="backpack-button__icon">🎒</span>
      {itemCount > 0 && (
        <span className="backpack-button__count">{itemCount}</span>
      )}
    </button>
  )
}

export default InventoryDrawer

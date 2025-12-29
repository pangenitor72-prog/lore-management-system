import { useState, useEffect, useCallback } from 'react'
import './GameToast.css'

/**
 * GameToast Component - The "Event" Layer
 *
 * Displays toast notifications for game events (item pickups, skill checks, etc.)
 *
 * Props:
 *   events: GameEvent[] - Events from backend response
 *   onItemAdded: () => void - Callback to trigger backpack animation
 */
export function GameToastContainer({ events = [], onItemAdded }) {
  const [toasts, setToasts] = useState([])

  // Process new events
  useEffect(() => {
    if (!events || events.length === 0) return

    const newToasts = events.map((event, index) => ({
      id: `${Date.now()}-${index}`,
      ...event,
      visible: true
    }))

    setToasts(prev => [...prev, ...newToasts])

    // Check if any items were added
    const hasItems = events.some(e => e.type === 'ITEM_ADDED')
    if (hasItems && onItemAdded) {
      onItemAdded()
    }
  }, [events, onItemAdded])

  // Auto-dismiss toasts
  const dismissToast = useCallback((id) => {
    setToasts(prev =>
      prev.map(t => t.id === id ? { ...t, visible: false } : t)
    )
    // Remove from DOM after animation
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 300)
  }, [])

  useEffect(() => {
    toasts.forEach(toast => {
      if (toast.visible) {
        const timer = setTimeout(() => {
          dismissToast(toast.id)
        }, 4000)
        return () => clearTimeout(timer)
      }
    })
  }, [toasts, dismissToast])

  if (toasts.length === 0) return null

  return (
    <div className="game-toast-container">
      {toasts.map(toast => (
        <GameToast
          key={toast.id}
          event={toast}
          visible={toast.visible}
          onDismiss={() => dismissToast(toast.id)}
        />
      ))}
    </div>
  )
}

/**
 * Individual Toast Notification
 */
function GameToast({ event, visible, onDismiss }) {
  const { icon, title, subtitle, className } = getToastContent(event)

  return (
    <div
      className={`game-toast ${className} ${visible ? 'game-toast--visible' : 'game-toast--hidden'}`}
      onClick={onDismiss}
    >
      <span className="game-toast__icon">{icon}</span>
      <div className="game-toast__content">
        <span className="game-toast__title">{title}</span>
        {subtitle && <span className="game-toast__subtitle">{subtitle}</span>}
      </div>
    </div>
  )
}

/**
 * Get toast display content based on event type
 */
function getToastContent(event) {
  const data = event.data || {}

  switch (event.type) {
    case 'ITEM_ADDED':
      return {
        icon: '📦',
        title: `+ ${data.item || 'Item'}`,
        subtitle: data.quantity > 1 ? `×${data.quantity}` : null,
        className: 'game-toast--item'
      }

    case 'ITEM_REMOVED':
      return {
        icon: '📤',
        title: `- ${data.item || 'Item'}`,
        subtitle: data.quantity > 1 ? `×${data.quantity}` : null,
        className: 'game-toast--item-removed'
      }

    case 'GOLD_CHANGED':
      const isGain = (data.amount || 0) > 0
      return {
        icon: '🪙',
        title: `${isGain ? '+' : ''}${data.amount || 0} Gold`,
        subtitle: data.total ? `Total: ${data.total}` : null,
        className: isGain ? 'game-toast--gold-gain' : 'game-toast--gold-loss'
      }

    case 'SKILL_CHECK':
      const success = data.success
      return {
        icon: success ? '✓' : '✗',
        title: `${data.skill || 'Check'} ${success ? 'Success' : 'Failed'}`,
        subtitle: `${data.roll || 0} + ${data.modifier || 0} = ${data.total || 0} vs DC ${data.dc || 0}`,
        className: success ? 'game-toast--success' : 'game-toast--fail'
      }

    case 'ATTACK_ROLL':
      return {
        icon: data.is_hit ? '⚔️' : '💨',
        title: data.is_hit ? 'Attack Hits!' : 'Attack Missed',
        subtitle: `Roll: ${data.total || 0}`,
        className: data.is_hit ? 'game-toast--success' : 'game-toast--fail'
      }

    case 'DAMAGE_DEALT':
      return {
        icon: '💥',
        title: `${data.damage || 0} ${data.damage_type || ''} Damage`,
        subtitle: null,
        className: 'game-toast--damage'
      }

    case 'DAMAGE_TAKEN':
      return {
        icon: '❤️‍🩹',
        title: `Took ${data.amount || 0} Damage`,
        subtitle: data.source || null,
        className: 'game-toast--damage-taken'
      }

    case 'HP_CHANGED':
      const isHeal = (data.change || 0) > 0
      return {
        icon: isHeal ? '💚' : '❤️',
        title: `${isHeal ? '+' : ''}${data.change || 0} HP`,
        subtitle: `${data.current}/${data.max}`,
        className: isHeal ? 'game-toast--heal' : 'game-toast--damage-taken'
      }

    case 'LEVEL_UP':
      return {
        icon: '⬆️',
        title: 'Level Up!',
        subtitle: `Now Level ${data.level || '?'}`,
        className: 'game-toast--level-up'
      }

    case 'LOCATION_CHANGED':
      return {
        icon: '📍',
        title: 'New Location',
        subtitle: data.location || 'Unknown',
        className: 'game-toast--location'
      }

    default:
      return {
        icon: 'ℹ️',
        title: event.type,
        subtitle: JSON.stringify(data),
        className: 'game-toast--info'
      }
  }
}

export default GameToastContainer

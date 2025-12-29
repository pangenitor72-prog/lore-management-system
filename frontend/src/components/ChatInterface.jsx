import { useState, useRef, useEffect, useCallback } from 'react'
import { useWebSocket, ConnectionState } from '../contexts/WebSocketContext'
import { PacingBar, InventoryDrawer, BackpackButton, GameToastContainer, MissionReport } from './game'
import './ChatInterface.css'

/**
 * ChatInterface Component - The Game Client
 *
 * Interactive game UI with:
 * - Pacing Layer (progress bar for ONE_SHOT sessions)
 * - Tactical Layer (inventory drawer)
 * - Event Layer (toast notifications)
 * - Mission Report (end screen)
 */

export function ChatInterface({
  // Session configuration
  sessionId = null,
  sessionScope = "ONE_SHOT",
  mode = "STORY",
  maxTurns = 20,
  // Character data (for RPG mode)
  character = null,
  // Initial inventory
  initialInventory = { items: [], gold: 0 },
  // Callbacks
  onReturnToMenu = () => {},
  onSaveSession = () => {},
}) {
  const { messages, sendMessage, connectionState } = useWebSocket()
  const safeMessages = Array.isArray(messages) ? messages : []

  const [inputValue, setInputValue] = useState('')
  const [currentTurn, setCurrentTurn] = useState(0)
  const [inventory, setInventory] = useState(initialInventory)
  const [pendingEvents, setPendingEvents] = useState([])
  const [sessionEnded, setSessionEnded] = useState(false)
  const [hasNewItems, setHasNewItems] = useState(false)

  // UI state
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [showMissionReport, setShowMissionReport] = useState(false)

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [safeMessages])

  // Focus input on mount (if not ended)
  useEffect(() => {
    if (!sessionEnded) {
      inputRef.current?.focus()
    }
  }, [sessionEnded])

  // Process backend response for events and state updates
  const processResponse = useCallback((response) => {
    if (!response) return

    // Extract turn count
    if (response.turn !== undefined) {
      setCurrentTurn(response.turn)
    } else {
      setCurrentTurn(prev => prev + 1)
    }

    // Extract events
    if (response.events && Array.isArray(response.events)) {
      setPendingEvents(response.events)

      // Update inventory based on events
      response.events.forEach(event => {
        if (event.type === 'ITEM_ADDED' && event.data) {
          setInventory(prev => ({
            ...prev,
            items: [...prev.items, {
              name: event.data.item,
              quantity: event.data.quantity || 1,
              type: event.data.type || 'misc'
            }]
          }))
        }
        if (event.type === 'GOLD_CHANGED' && event.data) {
          setInventory(prev => ({
            ...prev,
            gold: prev.gold + (event.data.amount || 0)
          }))
        }
      })
    }

    // Check for session end
    if (response.session_ended) {
      setSessionEnded(true)
      // Show mission report after a brief delay
      setTimeout(() => setShowMissionReport(true), 1500)
    }
  }, [])

  // Process incoming messages
  useEffect(() => {
    if (safeMessages.length > 0) {
      const lastMessage = safeMessages[safeMessages.length - 1]
      processResponse(lastMessage)
    }
  }, [safeMessages, processResponse])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (sessionEnded) return

    const trimmed = inputValue.trim()
    if (!trimmed) return

    console.log('UI: sending', trimmed)
    try {
      const result = await sendMessage('query', { query: trimmed })
      console.log('UI: sendMessage() returned', result)
      if (result) setInputValue('')
    } catch (err) {
      console.error('UI: send failed', err)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleItemAdded = useCallback(() => {
    setHasNewItems(true)
    setTimeout(() => setHasNewItems(false), 600)
  }, [])

  const getConnectionStatusClass = () => {
    switch (connectionState) {
      case ConnectionState.CONNECTED:
        return 'status--connected'
      case ConnectionState.CONNECTING:
        return 'status--connecting'
      default:
        return 'status--disconnected'
    }
  }

  const getConnectionStatusText = () => {
    switch (connectionState) {
      case ConnectionState.CONNECTED:
        return 'Connected'
      case ConnectionState.CONNECTING:
        return 'Connecting...'
      case ConnectionState.ERROR:
        return 'Connection Error'
      default:
        return 'Disconnected'
    }
  }

  // Calculate session stats for mission report
  const sessionStats = {
    turns: currentTurn,
    itemsCollected: inventory.items,
    goldEarned: inventory.gold,
    skillChecks: { successes: 0, failures: 0 },
    combats: { won: 0, fled: 0 },
    locationsVisited: [],
    finalNarrative: safeMessages.length > 0
      ? (safeMessages[safeMessages.length - 1]?.response || '')
      : ''
  }

  return (
    <div className="chat-interface chat-interface--game">
      {/* Pacing Bar (ONE_SHOT only) */}
      <PacingBar
        currentTurn={currentTurn}
        maxTurns={maxTurns}
        sessionScope={sessionScope}
      />

      {/* Header */}
      <header className="chat-header">
        <div className="chat-header__title">
          <span className="chat-header__icon">🎲</span>
          <h1>Adventure</h1>
        </div>
        <div className="chat-header__actions">
          <BackpackButton
            onClick={() => setIsDrawerOpen(true)}
            hasNewItems={hasNewItems}
            itemCount={inventory.items.length}
          />
          <div className="chat-header__status">
            <span className={`status-indicator ${getConnectionStatusClass()}`} />
            <span className="status-text">{getConnectionStatusText()}</span>
          </div>
        </div>
      </header>

      {/* Messages Container */}
      <div className="chat-messages">
        {safeMessages.length === 0 ? (
          <div className="chat-empty">
            <div className="chat-empty__icon">🗺️</div>
            <h2>Your Adventure Awaits</h2>
            <p>What do you do?</p>
          </div>
        ) : (
          <>
            {safeMessages.map((message, index) => {
              const isUser = message?.role === 'user'
              const text =
                message?.response ??
                message?.narrative ??
                message?.error ??
                message?.status ??
                (typeof message === 'string' ? message : JSON.stringify(message, null, 2))

              return (
                <div
                  key={message?.timestamp || message?.client_id || `msg-${index}`}
                  className={`chat-message ${isUser ? 'chat-message--user' : 'chat-message--assistant'}`}
                >
                  <div className="chat-message__avatar">
                    {isUser ? '🧑' : '📜'}
                  </div>
                  <div className="chat-message__content">
                    <span className="chat-message__role">
                      {isUser ? 'You' : 'DM'}
                    </span>
                    <div className="chat-message__text">{text}</div>
                  </div>
                </div>
              )
            })}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Form */}
      <form className="chat-input-form" onSubmit={handleSubmit}>
        <div className="chat-input-wrapper">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              sessionEnded
                ? "Your story has concluded..."
                : connectionState === ConnectionState.CONNECTED
                  ? "What do you do?"
                  : "Waiting for connection..."
            }
            disabled={sessionEnded || connectionState !== ConnectionState.CONNECTED}
            rows={1}
          />
          <button
            type="submit"
            className="chat-submit"
            disabled={!inputValue.trim() || sessionEnded || connectionState !== ConnectionState.CONNECTED}
          >
            <span>{sessionEnded ? 'Ended' : 'Act'}</span>
          </button>
        </div>
      </form>

      {/* Inventory Drawer (Tactical Layer) */}
      <InventoryDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        inventory={inventory}
        character={character}
        mode={mode}
      />

      {/* Toast Notifications (Event Layer) */}
      <GameToastContainer
        events={pendingEvents}
        onItemAdded={handleItemAdded}
      />

      {/* Mission Report (End Screen) */}
      <MissionReport
        isOpen={showMissionReport}
        sessionData={sessionStats}
        onReturnToMenu={onReturnToMenu}
        onSaveToChronicles={onSaveSession}
      />
    </div>
  )
}

export default ChatInterface

import { useState, useRef, useEffect } from 'react'
import { useWebSocket, ConnectionState } from '../contexts/WebSocketContext'
import './ChatInterface.css'

/**
 * ChatInterface Component
 * 
 * Interactive chat UI for querying the Lore Management System via Gemini socket.
 */

export function ChatInterface() {
  const { messages, sendMessage, connectionState } = useWebSocket()
  const safeMessages = Array.isArray(messages) ? messages : []

  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [safeMessages])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
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

  return (
    <div className="chat-interface">
      {/* Header */}
      <header className="chat-header">
        <div className="chat-header__title">
          <span className="chat-header__icon">📜</span>
          <h1>Lore Oracle</h1>
        </div>
        <div className="chat-header__status">
          <span className={`status-indicator ${getConnectionStatusClass()}`} />
          <span className="status-text">{getConnectionStatusText()}</span>
        </div>
      </header>

      {/* Messages Container */}
      <div className="chat-messages">
        {safeMessages.length === 0 ? (
          <div className="chat-empty">
            <div className="chat-empty__icon">🗺️</div>
            <h2>Welcome, Chronicler</h2>
            <p>Ask questions about the world's lore, characters, and history.</p>
          </div>
        ) : (
          <>
            {safeMessages.map((message, index) => (
              <pre key={index} className="chat-debug-message">
                {JSON.stringify(message, null, 2)}
              </pre>
            ))}
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
            placeholder={connectionState === ConnectionState.CONNECTED ? "Ask about the lore..." : "Waiting for connection..."}
            disabled={connectionState !== ConnectionState.CONNECTED}
            rows={1}
          />
          <button
            type="submit"
            className="chat-submit"
            disabled={!inputValue.trim() || connectionState !== ConnectionState.CONNECTED}
          >
            <span>Send</span>
          </button>
        </div>
      </form>
    </div>
  )
}

export default ChatInterface


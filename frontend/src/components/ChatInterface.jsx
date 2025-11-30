import { useState, useRef, useEffect } from 'react'
import { useChat } from '../hooks/useChat'
import { useWebSocket, ConnectionState } from '../contexts/WebSocketContext'
import './ChatInterface.css'

/**
 * ChatInterface Component
 * 
 * Interactive chat UI for querying the Lore Management System.
 * Uses the useChat hook to manage messages and WebSocket communication.
 */

export function ChatInterface() {
  const { messages, sendQuery, clearMessages, isStreaming, isConnected } = useChat()
  const { connectionState } = useWebSocket()
  
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!inputValue.trim() || isStreaming || !isConnected) return
    
    sendQuery(inputValue)
    setInputValue('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const getConnectionStatusClass = () => {
    switch (connectionState) {
      case ConnectionState.CONNECTED: return 'status--connected'
      case ConnectionState.CONNECTING:
      case ConnectionState.RECONNECTING: return 'status--connecting'
      default: return 'status--disconnected'
    }
  }

  const getConnectionStatusText = () => {
    switch (connectionState) {
      case ConnectionState.CONNECTED: return 'Connected'
      case ConnectionState.CONNECTING: return 'Connecting...'
      case ConnectionState.RECONNECTING: return 'Reconnecting...'
      case ConnectionState.ERROR: return 'Connection Error'
      default: return 'Disconnected'
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
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="chat-empty__icon">🗺️</div>
            <h2>Welcome, Chronicler</h2>
            <p>Ask questions about the world's lore, characters, and history.</p>
            <div className="chat-empty__suggestions">
              <button onClick={() => setInputValue('Who is the Black King?')}>
                Who is the Black King?
              </button>
              <button onClick={() => setInputValue('Tell me about the Sunken City')}>
                Tell me about the Sunken City
              </button>
              <button onClick={() => setInputValue('What happened in Year 298?')}>
                What happened in Year 298?
              </button>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <div
                key={message.id}
                className={`chat-message chat-message--${message.role} ${
                  message.isError ? 'chat-message--error' : ''
                } ${message.isStreaming ? 'chat-message--streaming' : ''}`}
              >
                <div className="chat-message__avatar">
                  {message.role === 'user' ? '🧙' : message.role === 'system' ? '⚠️' : '📖'}
                </div>
                <div className="chat-message__content">
                  <div className="chat-message__role">
                    {message.role === 'user' ? 'You' : message.role === 'system' ? 'System' : 'Lore Oracle'}
                  </div>
                  <div className="chat-message__text">
                    {message.content}
                    {message.isStreaming && <span className="typing-cursor">▊</span>}
                  </div>
                  {message.metadata?.sources && (
                    <div className="chat-message__sources">
                      <span>Sources:</span>
                      {message.metadata.sources.map((source, i) => (
                        <span key={i} className="source-tag">{source}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
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
            placeholder={isConnected ? "Ask about the lore..." : "Waiting for connection..."}
            disabled={!isConnected || isStreaming}
            rows={1}
          />
          <button
            type="submit"
            className="chat-submit"
            disabled={!inputValue.trim() || !isConnected || isStreaming}
          >
            {isStreaming ? (
              <span className="loading-spinner" />
            ) : (
              <span>Send</span>
            )}
          </button>
        </div>
        {messages.length > 0 && (
          <button
            type="button"
            className="chat-clear"
            onClick={clearMessages}
          >
            Clear History
          </button>
        )}
      </form>
    </div>
  )
}

export default ChatInterface


import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'

/**
 * Gemini WebSocket Context - single socket for chat
 */

const WebSocketContext = createContext({
  messages: [],
  sendMessage: () => false,
  connectionState: 'disconnected',
})

// Connection states for UI feedback
export const ConnectionState = {
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  RECONNECTING: 'reconnecting',
  ERROR: 'error',
}

// WebSocket URL configuration (env override for deploy)
const getWebSocketBaseUrl = () => {
  if (import.meta.env.VITE_WS_BASE_URL) return import.meta.env.VITE_WS_BASE_URL
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}`
}

export function WebSocketProvider({ children }) {
  const wsRef = useRef(null)
  const hasConnectedRef = useRef(false)
  const clientIdRef = useRef(crypto.randomUUID())
  const clientId = clientIdRef.current
  const [messages, setMessages] = useState([])
  const [connectionState, setConnectionState] = useState(ConnectionState.DISCONNECTED)

  useEffect(() => {
    if (hasConnectedRef.current) return
    hasConnectedRef.current = true

    setConnectionState(ConnectionState.CONNECTING)
    const wsBase = getWebSocketBaseUrl()
    const ws = new WebSocket(`${wsBase}/ws/gemini?client_id=${clientId}`)
    wsRef.current = ws

    ws.onopen = () => setConnectionState(ConnectionState.CONNECTED)
    ws.onclose = () => setConnectionState(ConnectionState.DISCONNECTED)
    ws.onerror = () => setConnectionState(ConnectionState.ERROR)
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setMessages((prev) => [...prev, data])
    }

    // Explicitly keep the socket open during StrictMode remounts
    return () => {}
  }, [clientId])

  // Legacy API compatibility: return a no-op unsubscribe
  const subscribeToChannel = useCallback(() => () => {}, [])

  /**
   * Send a message to a specific channel
   */
  const sendMessage = useCallback((channel, payload) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return false
    if (channel !== 'query') return false
    if (!payload || typeof payload !== 'object') return false
    if (!payload.query) return false

    try {
      wsRef.current.send(JSON.stringify({ 
        query: payload.query,
        session_id: payload.session_id 
      }))
      return true
    } catch {
      return false
    }
  }, [])

  const contextValue = {
    messages,
    sendMessage,
    connectionState,
    subscribeToChannel,
  }

  return (
    <WebSocketContext.Provider value={contextValue}>
      {children}
    </WebSocketContext.Provider>
  )
}

/**
 * Hook to access WebSocket context
 */
export function useWebSocket() {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}

export default WebSocketContext

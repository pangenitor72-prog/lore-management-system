import { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react'

/**
 * WebSocket Context - The Nervous System
 * 
 * Manages a single, persistent WebSocket connection that multiplexes channels:
 * - query_events: Chat/query responses from the QueryAgent
 * - auditor_events: Contradiction detection and audit events
 * - ingestion_events: File processing progress
 */

const WebSocketContext = createContext(null)

// Connection states for UI feedback
export const ConnectionState = {
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  DISCONNECTED: 'disconnected',
  RECONNECTING: 'reconnecting',
  ERROR: 'error',
}

// WebSocket URL configuration
const WS_BASE_URL = 'ws://localhost:8000'
const DEFAULT_CHANNELS = ['query_events', 'auditor_events', 'ingestion_events']

export function WebSocketProvider({ children }) {
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectAttempts = useRef(0)
  
  const [connectionState, setConnectionState] = useState(ConnectionState.DISCONNECTED)
  const [lastError, setLastError] = useState(null)
  
  // Channel-specific message handlers (set by consumers)
  const queryHandlersRef = useRef(new Set())
  const auditorHandlersRef = useRef(new Set())
  const ingestionHandlersRef = useRef(new Set())

  /**
   * Route incoming messages to appropriate handlers based on _channel
   */
  const routeMessage = useCallback((message) => {
    const { _channel, ...payload } = message
    
    switch (_channel) {
      case 'query_events':
        queryHandlersRef.current.forEach(handler => handler(payload))
        break
      case 'auditor_events':
        auditorHandlersRef.current.forEach(handler => handler(payload))
        break
      case 'ingestion_events':
        ingestionHandlersRef.current.forEach(handler => handler(payload))
        break
      default:
        console.warn('[WS] Unknown channel:', _channel, payload)
    }
  }, [])

  /**
   * Establish WebSocket connection with auto-reconnect
   */
  const connect = useCallback(() => {
    // Don't reconnect if already connected
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    setConnectionState(ConnectionState.CONNECTING)
    
    const channelParams = DEFAULT_CHANNELS.join(',')
    const wsUrl = `${WS_BASE_URL}/ws/events?channels=${channelParams}`
    
    console.log('[WS] Connecting to:', wsUrl)
    
    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('[WS] Connected successfully')
        setConnectionState(ConnectionState.CONNECTED)
        setLastError(null)
        reconnectAttempts.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          routeMessage(message)
        } catch (err) {
          console.error('[WS] Failed to parse message:', err, event.data)
        }
      }

      ws.onerror = (error) => {
        console.error('[WS] WebSocket error:', error)
        setLastError('Connection error')
        setConnectionState(ConnectionState.ERROR)
      }

      ws.onclose = (event) => {
        console.log('[WS] Connection closed:', event.code, event.reason)
        wsRef.current = null
        
        if (event.code !== 1000) {
          // Abnormal closure - attempt reconnect with exponential backoff
          setConnectionState(ConnectionState.RECONNECTING)
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
          reconnectAttempts.current++
          
          console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})`)
          reconnectTimeoutRef.current = setTimeout(connect, delay)
        } else {
          setConnectionState(ConnectionState.DISCONNECTED)
        }
      }
    } catch (err) {
      console.error('[WS] Failed to create WebSocket:', err)
      setLastError(err.message)
      setConnectionState(ConnectionState.ERROR)
    }
  }, [routeMessage])

  /**
   * Disconnect and cleanup
   */
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnecting')
      wsRef.current = null
    }
    
    setConnectionState(ConnectionState.DISCONNECTED)
  }, [])

  /**
   * Send a message to a specific channel
   */
  const sendMessage = useCallback((channel, payload) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[WS] Cannot send - not connected')
      return false
    }

    const message = {
      _channel: channel,
      ...payload,
    }

    try {
      wsRef.current.send(JSON.stringify(message))
      return true
    } catch (err) {
      console.error('[WS] Failed to send message:', err)
      return false
    }
  }, [])

  /**
   * Subscribe to a specific channel's messages
   */
  const subscribeToChannel = useCallback((channel, handler) => {
    const handlersRef = {
      query_events: queryHandlersRef,
      auditor_events: auditorHandlersRef,
      ingestion_events: ingestionHandlersRef,
    }[channel]

    if (!handlersRef) {
      console.error('[WS] Unknown channel:', channel)
      return () => {}
    }

    handlersRef.current.add(handler)
    
    // Return unsubscribe function
    return () => {
      handlersRef.current.delete(handler)
    }
  }, [])

  // Auto-connect on mount
  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  const contextValue = {
    connectionState,
    lastError,
    sendMessage,
    subscribeToChannel,
    connect,
    disconnect,
    isConnected: connectionState === ConnectionState.CONNECTED,
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

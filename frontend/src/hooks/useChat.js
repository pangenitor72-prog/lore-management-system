import { useState, useCallback, useEffect, useRef } from 'react'
import { useWebSocket } from '../contexts/WebSocketContext'

/**
 * useChat Hook - Chat Interface Voice
 * 
 * Manages chat state and provides methods to interact with the QueryAgent
 * via the WebSocket query_events channel.
 */

// Message types from backend
const MessageType = {
  QUERY: 'query',
  RESPONSE: 'response',
  STREAMING_START: 'streaming_start',
  STREAMING_CHUNK: 'streaming_chunk',
  STREAMING_END: 'streaming_end',
  ERROR: 'error',
}

export function useChat() {
  const { subscribeToChannel, sendMessage, isConnected } = useWebSocket()
  
  const [messages, setMessages] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingMessageId, setStreamingMessageId] = useState(null)
  const messageIdCounter = useRef(0)

  /**
   * Generate a unique message ID
   */
  const generateMessageId = useCallback(() => {
    messageIdCounter.current++
    return `msg-${Date.now()}-${messageIdCounter.current}`
  }, [])

  /**
   * Handle incoming messages from query_events channel
   */
  const handleQueryEvent = useCallback((payload) => {
    const { type, content, message_id, error, metadata } = payload

    switch (type) {
      case MessageType.STREAMING_START:
        // Create a new assistant message placeholder
        const newMsgId = message_id || generateMessageId()
        setStreamingMessageId(newMsgId)
        setIsStreaming(true)
        setMessages(prev => [...prev, {
          id: newMsgId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          isStreaming: true,
          metadata,
        }])
        break

      case MessageType.STREAMING_CHUNK:
        // Append content to the streaming message
        setMessages(prev => prev.map(msg => 
          msg.id === streamingMessageId
            ? { ...msg, content: msg.content + (content || '') }
            : msg
        ))
        break

      case MessageType.STREAMING_END:
        // Finalize the streaming message
        setMessages(prev => prev.map(msg =>
          msg.id === streamingMessageId
            ? { ...msg, isStreaming: false, metadata: { ...msg.metadata, ...metadata } }
            : msg
        ))
        setIsStreaming(false)
        setStreamingMessageId(null)
        break

      case MessageType.RESPONSE:
        // Non-streaming response (full message at once)
        const msgId = message_id || generateMessageId()
        setMessages(prev => [...prev, {
          id: msgId,
          role: 'assistant',
          content: content || '',
          timestamp: new Date(),
          isStreaming: false,
          metadata,
        }])
        break

      case MessageType.ERROR:
        // Handle error responses
        setMessages(prev => [...prev, {
          id: generateMessageId(),
          role: 'system',
          content: error || 'An error occurred',
          timestamp: new Date(),
          isError: true,
        }])
        setIsStreaming(false)
        setStreamingMessageId(null)
        break

      default:
        console.warn('[useChat] Unknown message type:', type, payload)
    }
  }, [streamingMessageId, generateMessageId])

  /**
   * Subscribe to query_events channel
   */
  useEffect(() => {
    const unsubscribe = subscribeToChannel('query_events', handleQueryEvent)
    return unsubscribe
  }, [subscribeToChannel, handleQueryEvent])

  /**
   * Send a query to the backend
   */
  const sendQuery = useCallback((text) => {
    if (!text.trim() || !isConnected) {
      return false
    }

    // Add user message to local state
    const userMsgId = generateMessageId()
    setMessages(prev => [...prev, {
      id: userMsgId,
      role: 'user',
      content: text,
      timestamp: new Date(),
    }])

    // Send to backend via WebSocket
    const success = sendMessage('query_events', {
      type: 'query',
      content: text,
      message_id: userMsgId,
    })

    return success
  }, [isConnected, sendMessage, generateMessageId])

  /**
   * Clear all messages
   */
  const clearMessages = useCallback(() => {
    setMessages([])
    setIsStreaming(false)
    setStreamingMessageId(null)
  }, [])

  return {
    messages,
    sendQuery,
    clearMessages,
    isStreaming,
    isConnected,
  }
}

export default useChat


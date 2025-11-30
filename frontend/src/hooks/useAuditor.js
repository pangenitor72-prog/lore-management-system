import { useState, useCallback, useEffect, useRef } from 'react'
import { useWebSocket } from '../contexts/WebSocketContext'

/**
 * useAuditor Hook - Dashboard Auditor Events
 * 
 * Listens to auditor_events channel for real-time contradiction
 * detection and audit notifications.
 */

// Event types from auditor
const AuditorEventType = {
  NEW_CONTRADICTION: 'new_contradiction',
  CONTRADICTION_RESOLVED: 'contradiction_resolved',
  CONTRADICTION_UPDATED: 'contradiction_updated',
  AUDIT_STARTED: 'audit_started',
  AUDIT_COMPLETED: 'audit_completed',
  ENTITY_FLAGGED: 'entity_flagged',
}

export function useAuditor() {
  const { subscribeToChannel, isConnected } = useWebSocket()
  
  const [contradictions, setContradictions] = useState([])
  const [recentEvents, setRecentEvents] = useState([])
  const [isAuditing, setIsAuditing] = useState(false)
  const [stats, setStats] = useState({
    totalContradictions: 0,
    pendingCount: 0,
    criticalCount: 0,
  })

  const eventIdCounter = useRef(0)

  /**
   * Generate unique event ID
   */
  const generateEventId = useCallback(() => {
    eventIdCounter.current++
    return `evt-${Date.now()}-${eventIdCounter.current}`
  }, [])

  /**
   * Handle incoming auditor events
   */
  const handleAuditorEvent = useCallback((payload) => {
    const { type, data, timestamp } = payload

    // Add to recent events log (keep last 50)
    const event = {
      id: generateEventId(),
      type,
      data,
      timestamp: timestamp || new Date().toISOString(),
      isNew: true,
    }
    
    setRecentEvents(prev => [event, ...prev.slice(0, 49)])

    switch (type) {
      case AuditorEventType.NEW_CONTRADICTION:
        // Add new contradiction to the top of the list
        const newContradiction = {
          ...data,
          isNew: true,
          receivedAt: new Date(),
        }
        setContradictions(prev => [newContradiction, ...prev])
        
        // Update stats
        setStats(prev => ({
          ...prev,
          totalContradictions: prev.totalContradictions + 1,
          pendingCount: prev.pendingCount + 1,
          criticalCount: data.severity === 'CRITICAL' 
            ? prev.criticalCount + 1 
            : prev.criticalCount,
        }))
        break

      case AuditorEventType.CONTRADICTION_RESOLVED:
        // Update contradiction status
        setContradictions(prev => prev.map(c =>
          c.contradiction_id === data.contradiction_id
            ? { ...c, status: 'RESOLVED', isNew: false }
            : c
        ))
        setStats(prev => ({
          ...prev,
          pendingCount: Math.max(0, prev.pendingCount - 1),
        }))
        break

      case AuditorEventType.CONTRADICTION_UPDATED:
        // Update contradiction data
        setContradictions(prev => prev.map(c =>
          c.contradiction_id === data.contradiction_id
            ? { ...c, ...data, isNew: false }
            : c
        ))
        break

      case AuditorEventType.AUDIT_STARTED:
        setIsAuditing(true)
        break

      case AuditorEventType.AUDIT_COMPLETED:
        setIsAuditing(false)
        if (data?.stats) {
          setStats(prev => ({ ...prev, ...data.stats }))
        }
        break

      case AuditorEventType.ENTITY_FLAGGED:
        // Could trigger a notification or update entity list
        console.log('[useAuditor] Entity flagged:', data)
        break

      default:
        console.warn('[useAuditor] Unknown event type:', type, payload)
    }
  }, [generateEventId])

  /**
   * Subscribe to auditor_events channel
   */
  useEffect(() => {
    const unsubscribe = subscribeToChannel('auditor_events', handleAuditorEvent)
    return unsubscribe
  }, [subscribeToChannel, handleAuditorEvent])

  /**
   * Mark a contradiction as seen (remove "new" badge)
   */
  const markAsSeen = useCallback((contradictionId) => {
    setContradictions(prev => prev.map(c =>
      c.contradiction_id === contradictionId
        ? { ...c, isNew: false }
        : c
    ))
  }, [])

  /**
   * Clear all contradictions (local state only)
   */
  const clearContradictions = useCallback(() => {
    setContradictions([])
  }, [])

  /**
   * Get count of new (unseen) contradictions
   */
  const newCount = contradictions.filter(c => c.isNew).length

  return {
    contradictions,
    recentEvents,
    isAuditing,
    stats,
    newCount,
    markAsSeen,
    clearContradictions,
    isConnected,
  }
}

export default useAuditor


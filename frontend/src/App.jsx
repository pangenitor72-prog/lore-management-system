import { useState, useEffect, useCallback } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import { useWebSocket, ConnectionState } from './contexts/WebSocketContext'
import ChatInterface from './components/ChatInterface'
import Dashboard from './components/Dashboard'
import LoreUpload from './components/LoreUpload'
import Library from './components/Library'
import AIRpg from './components/AIRpg'
import { useAuditor } from './hooks/useAuditor'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
const VERSION_CHECK_INTERVAL = 5 * 60 * 1000 // Check every 5 minutes
const STORED_VERSION_KEY = 'lms_app_version'

/**
 * Main App Component
 *
 * Provides layout shell with navigation between Chat and Dashboard views.
 */

// Announcement banner config - set to null to hide
const ANNOUNCEMENT = {
  id: 'jan-2026-update',  // Change this to show a new announcement
  message: "Sorry for any recent downtime! We've been debugging, adding new features, and improving the game. Thanks for your patience!",
  type: 'info'  // 'info', 'warning', 'success'
}

function App() {
  const { connectionState } = useWebSocket()
  const { newCount } = useAuditor()
  const [updateAvailable, setUpdateAvailable] = useState(false)
  const [showAnnouncement, setShowAnnouncement] = useState(() => {
    if (!ANNOUNCEMENT) return false
    const dismissed = localStorage.getItem(`announcement_dismissed_${ANNOUNCEMENT.id}`)
    return !dismissed
  })

  const dismissAnnouncement = () => {
    if (ANNOUNCEMENT) {
      localStorage.setItem(`announcement_dismissed_${ANNOUNCEMENT.id}`, 'true')
    }
    setShowAnnouncement(false)
  }

  const checkForUpdates = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/version`, { cache: 'no-store' })
      if (res.ok) {
        const data = await res.json()
        const serverVersion = data.version
        const storedVersion = localStorage.getItem(STORED_VERSION_KEY)

        if (!storedVersion) {
          // First visit - store current version
          localStorage.setItem(STORED_VERSION_KEY, serverVersion)
        } else if (serverVersion !== storedVersion && serverVersion !== 'unknown') {
          // Version changed - show update banner
          setUpdateAvailable(true)
        }
      }
    } catch {
      // Silent fail - don't disrupt user experience
    }
  }, [])

  const handleRefresh = () => {
    // Clear stored version so it gets updated on next load
    localStorage.removeItem(STORED_VERSION_KEY)
    window.location.reload()
  }

  useEffect(() => {
    // Check on mount
    checkForUpdates()

    // Check periodically
    const interval = setInterval(checkForUpdates, VERSION_CHECK_INTERVAL)
    return () => clearInterval(interval)
  }, [checkForUpdates])

  return (
    <div className="app">
      {/* Announcement Banner */}
      {showAnnouncement && ANNOUNCEMENT && (
        <div className={`announcement-banner announcement-banner--${ANNOUNCEMENT.type}`}>
          <span className="announcement-banner__message">{ANNOUNCEMENT.message}</span>
          <button onClick={dismissAnnouncement} className="announcement-banner__dismiss" aria-label="Dismiss">
            &times;
          </button>
        </div>
      )}

      {/* Update Available Banner */}
      {updateAvailable && (
        <div className="update-banner">
          <span>A new version is available!</span>
          <button onClick={handleRefresh} className="update-banner__btn">
            Refresh Now
          </button>
        </div>
      )}

      {/* Navigation Sidebar */}
      <nav className="app-nav">
        <div className="app-nav__brand">
          <span className="brand-icon">🧥</span>
          <span className="brand-text">Mantle</span>
        </div>

        <div className="app-nav__links">
          <NavLink 
            to="/play"
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}
          >
            <span className="nav-link__icon">🎲</span>
            <span className="nav-link__text">Play</span>
          </NavLink>

          <NavLink 
            to="/" 
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}
          >
            <span className="nav-link__icon">💬</span>
            <span className="nav-link__text">Chat</span>
          </NavLink>

          <NavLink 
            to="/library" 
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}
          >
            <span className="nav-link__icon">🏛️</span>
            <span className="nav-link__text">Library</span>
          </NavLink>

          <NavLink 
            to="/dashboard" 
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}
          >
            <span className="nav-link__icon">🛡️</span>
            <span className="nav-link__text">Dashboard</span>
            {newCount > 0 && (
              <span className="nav-link__badge">{newCount}</span>
            )}
          </NavLink>

          <NavLink 
            to="/upload" 
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}
          >
            <span className="nav-link__icon">📤</span>
            <span className="nav-link__text">Upload Lore</span>
          </NavLink>
        </div>

        <div className="app-nav__footer">
          <div className="connection-status">
            <span className={`connection-dot ${
              connectionState === ConnectionState.CONNECTED 
                ? 'connection-dot--connected' 
                : connectionState === ConnectionState.RECONNECTING
                  ? 'connection-dot--reconnecting'
                  : ''
            }`} />
            <span className="connection-text">
              {connectionState === ConnectionState.CONNECTED && 'Connected'}
              {connectionState === ConnectionState.CONNECTING && 'Connecting...'}
              {connectionState === ConnectionState.RECONNECTING && 'Reconnecting...'}
              {connectionState === ConnectionState.DISCONNECTED && 'Disconnected'}
              {connectionState === ConnectionState.ERROR && 'Error'}
            </span>
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="app-main">
        <Routes>
          <Route path="/" element={<ChatInterface />} />
          <Route path="/play" element={<AIRpg />} />
          <Route path="/library" element={<Library />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/upload" element={<LoreUpload />} />
        </Routes>
      </main>
    </div>
  )
}

export default App


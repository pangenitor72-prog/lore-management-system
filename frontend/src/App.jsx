import { Routes, Route, NavLink } from 'react-router-dom'
import { useWebSocket, ConnectionState } from './contexts/WebSocketContext'
import ChatInterface from './components/ChatInterface'
import Dashboard from './components/Dashboard'
import LoreUpload from './components/LoreUpload'
import { useAuditor } from './hooks/useAuditor'
import './App.css'

/**
 * Main App Component
 * 
 * Provides layout shell with navigation between Chat and Dashboard views.
 */

function App() {
  const { connectionState } = useWebSocket()
  const { newCount } = useAuditor()

  return (
    <div className="app">
      {/* Navigation Sidebar */}
      <nav className="app-nav">
        <div className="app-nav__brand">
          <span className="brand-icon">📚</span>
          <span className="brand-text">LMS</span>
        </div>

        <div className="app-nav__links">
          <NavLink 
            to="/" 
            className={({ isActive }) => `nav-link ${isActive ? 'nav-link--active' : ''}`}
          >
            <span className="nav-link__icon">💬</span>
            <span className="nav-link__text">Chat</span>
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
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/upload" element={<LoreUpload />} />
        </Routes>
      </main>
    </div>
  )
}

export default App


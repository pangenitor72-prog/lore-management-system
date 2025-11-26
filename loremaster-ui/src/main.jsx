import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { WebSocketProvider } from './contexts/WebSocketContext.jsx'; // Import WebSocketProvider

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <WebSocketProvider> {/* Wrap App with WebSocketProvider */}
      <App />
    </WebSocketProvider>
  </React.StrictMode>,
)
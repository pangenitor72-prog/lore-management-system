import React, { useState, useCallback, useEffect } from 'react';
import ChatInterface from './components/ChatInterface';
import WelcomeScreen from './components/WelcomeScreen';
import UploadContext from './components/UploadContext';
import SearchContext from './components/SearchContext';
import EntityDetailContext from './components/EntityDetailContext';
import ContradictionContext from './components/ContradictionContext';
import { useWebSocket } from './contexts/WebSocketContext'; // Import useWebSocket

function App() {
  const { sendMessage } = useWebSocket();
  const [context, setContext] = useState('welcome'); // Default context
  const [actionHistory, setActionHistory] = useState([]);
  const [canUndo, setCanUndo] = useState(false);

  // Function to record actions
  const recordAction = useCallback((actionType, beforeState, description) => {
    setActionHistory((prevHistory) => {
      const newHistory = [...prevHistory, { type: actionType, before: beforeState, description, timestamp: Date.now() }];
      if (newHistory.length > 10) { // Keep only last 10 actions
        return newHistory.slice(newHistory.length - 10);
      }
      return newHistory;
    });
  }, []);

  useEffect(() => {
    setCanUndo(actionHistory.length > 0);
  }, [actionHistory]);

  // Function to perform undo
  const handleUndo = useCallback(async () => {
    if (!canUndo) return;

    const lastAction = actionHistory[actionHistory.length - 1];
    // Call backend to restore state
    try {
      // Assuming a REST API for undo, will need to confirm with backend spec
      const response = await fetch('/api/undo', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(lastAction),
      });

      if (!response.ok) {
        throw new Error(`Undo failed: ${response.status}`);
      }

      const result = await response.json();
      if (result.success) {
        setActionHistory((prevHistory) => prevHistory.slice(0, prevHistory.length - 1)); // Remove last action
        // Here you would typically trigger a refresh of the UI state based on the restored backend state
        // For now, we'll just log and potentially change context if needed
        console.log('Undo successful:', result.restored_state);
        // Example: if undoing an upload, maybe go back to welcome screen or show upload context
        // setContext('welcome');
      } else {
        console.error('Undo was not successful:', result);
      }
    } catch (error) {
      console.error('Error during undo:', error);
      alert(`Undo failed: ${error.message}`);
    }
  }, [actionHistory, canUndo]);

  // Keyboard shortcut for undo (Ctrl+Z)
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.ctrlKey && event.key === 'z') {
        event.preventDefault(); // Prevent browser undo
        handleUndo();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleUndo]);


  // This will later be driven by WebSocket messages
  const renderDynamicContent = () => {
    switch (context) {
      case 'welcome':
        return <WelcomeScreen />;
      case 'upload':
        return <UploadContext />;
      case 'search':
        return <SearchContext />;
      case 'entity_detail':
        return <EntityDetailContext />;
      case 'contradiction':
        return <ContradictionContext />;
      default:
        return <WelcomeScreen />;
    }
  };

  return (
    <div className="app-container">
      {/* Placeholder Undo Button */}
      <button
        onClick={handleUndo}
        disabled={!canUndo}
        style={{
          position: 'absolute',
          top: '10px',
          right: '10px',
          padding: '8px 15px',
          backgroundColor: '#8b7355',
          color: '#f4e8d0',
          border: 'none',
          borderRadius: '5px',
          cursor: 'pointer',
          opacity: canUndo ? 1 : 0.5,
        }}
      >
        Undo (Ctrl+Z)
      </button>

      <div className="dynamic-canvas">
        {renderDynamicContent()}
      </div>
      <ChatInterface />
    </div>
  );
}

export default App;

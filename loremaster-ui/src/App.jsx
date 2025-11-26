import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import ChatInterface from './components/ChatInterface';
import WelcomeScreen from './components/WelcomeScreen';
import UploadContext from './components/UploadContext';
import SearchContext from './components/SearchContext';
import ContradictionContext from './components/ContradictionContext';
import EntityDetailContext from './components/EntityDetailContext';
import CanonDecisionContext from './components/CanonDecisionContext';
import DashboardContext from './components/DashboardContext';
import QuickActionsBar from './components/QuickActionsBar'; // Import QuickActionsBar
import ActionButton from './components/ActionButton'; // Import ActionButton

function App() {
  const [currentContext, setCurrentContext] = useState(null);
  const [contextData, setContextData] = useState(null);
  const [messages, setMessages] = useState([
    { sender: 'gemini', text: "Welcome to your Lore Management System, Jim. I'm here to help organize 30 years of campaign history. Let's start by uploading some files." },
  ]);
  const [availableActions, setAvailableActions] = useState([]);
  const [canUndo, setCanUndo] = useState(false);
  const ws = useRef(null);

  const sendMessageToGemini = useCallback((message) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected.');
      // Optionally, queue messages or show an error to the user
    }
  }, []);

  const handleSendMessage = (text) => {
    setMessages((prevMessages) => [...prevMessages, { sender: 'user', text }]);
    sendMessageToGemini({
      type: 'user_message',
      text: text,
      current_context: currentContext,
      current_state: {} // TODO: Populate current state
    });
  };

  const handleActionClick = (actionId) => {
    // For now, only handle the undo action
    if (actionId === 'undo') {
      sendMessageToGemini({
        type: 'action',
        action_id: 'undo',
        params: {} // Undo typically doesn't need params from frontend
      });
      setMessages((prevMessages) => [...prevMessages, { sender: 'user', text: "Undo last action" }]);
    }
    // TODO: Handle other actions based on actionId
  };

  useEffect(() => {
    const connectWs = () => {
      ws.current = new WebSocket('ws://localhost:8000/ws/gemini');

      ws.current.onopen = () => {
        console.log('WebSocket Connected');
        // Initial message or state sync could go here
      };

      ws.current.onmessage = (event) => {
        const response = JSON.parse(event.data);
        console.log('Received from Gemini:', response);

        if (response.text) {
          setMessages((prevMessages) => [...prevMessages, { sender: 'gemini', text: response.text }]);
        }
        
        if (response.context) {
          setCurrentContext(response.context);
          setContextData(response.data);
        }

        if (response.actions) {
          setAvailableActions(response.actions);
          // Check if undo action is available and update canUndo state
          const undoAction = response.actions.find(action => action.id === 'undo');
          setCanUndo(!!undoAction);
        }
      };

      ws.current.onclose = (event) => {
        console.log('WebSocket Disconnected:', event);
        // Attempt to reconnect after a delay
        setTimeout(connectWs, 3000);
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket Error:', error);
        ws.current.close(); // Close to trigger onclose and reconnect logic
      };
    };

    connectWs();

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [sendMessageToGemini]);

  const ContextIndicator = () => (
    <div className="context-indicator">
      <span>Context: {currentContext || 'Welcome'}</span>
    </div>
  );

  const StatusCorner = () => (
    <div className="status-corner">
      <span>Status: OK</span>
    </div>
  );

  const DynamicCanvas = ({ context, data }) => {
    let content;
    switch (context) {
      case 'upload':
        content = <UploadContext data={data} setCurrentContext={setCurrentContext} />;
        break;
      case 'search':
        content = <SearchContext data={data} />;
        break;
      case 'contradiction':
        content = <ContradictionContext data={data} />;
        break;
      case 'entity_detail':
        content = <EntityDetailContext data={data} />;
        break;
      case 'canon_decision':
        content = <CanonDecisionContext data={data} />;
        break;
      case 'dashboard':
        content = <DashboardContext data={data} />;
        break;
      default:
        content = <WelcomeScreen />;
    }
    return <div className="dynamic-canvas">{content}</div>;
  };

  return (
    <div className="app-container">
      <QuickActionsBar canUndo={canUndo} actions={availableActions} onActionClick={handleActionClick} />
      <ContextIndicator currentContext={currentContext} />
      <StatusCorner />
      <DynamicCanvas context={currentContext} data={contextData} />
      <ChatInterface messages={messages} onSendMessage={handleSendMessage} />
    </div>
  );
}

export default App;
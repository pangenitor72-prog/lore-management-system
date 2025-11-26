import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

const WebSocketContext = createContext(null);

export const useWebSocket = () => useContext(WebSocketContext);

export const WebSocketProvider = ({ children }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);
  const messageQueue = useRef([]); // Queue for messages sent while offline

  const connect = useCallback(() => {
    if (ws.current && (ws.current.readyState === WebSocket.OPEN || ws.current.readyState === WebSocket.CONNECTING)) {
      return; // Already connected or connecting
    }

    ws.current = new WebSocket('ws://localhost:8000/ws/gemini');

    ws.current.onopen = () => {
      console.log('WebSocket Connected');
      setIsConnected(true);
      clearTimeout(reconnectTimeout.current);
      // Send any queued messages
      while (messageQueue.current.length > 0) {
        const message = messageQueue.current.shift();
        ws.current.send(JSON.stringify(message));
      }
    };

    ws.current.onmessage = (event) => {
      setLastMessage(JSON.parse(event.data));
    };

    ws.current.onclose = () => {
      console.log('WebSocket Disconnected');
      setIsConnected(false);
      reconnectTimeout.current = setTimeout(() => {
        console.log('Attempting to reconnect...');
        connect();
      }, 3000); // Reconnect after 3 seconds
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket Error:', error);
      ws.current.close();
    };
  }, []);

  const sendMessage = useCallback((message) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected. Queuing message:', message);
      messageQueue.current.push(message); // Queue message for when connection is established
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (ws.current) {
        ws.current.close();
      }
      clearTimeout(reconnectTimeout.current);
    };
  }, [connect]);

  const value = {
    isConnected,
    lastMessage,
    sendMessage,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

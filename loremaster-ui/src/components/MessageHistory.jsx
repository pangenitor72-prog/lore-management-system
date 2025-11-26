import React from 'react';
import GeminiMessage from './GeminiMessage';
import UserMessage from './UserMessage';

function MessageHistory({ messages }) {
  return (
    <div className="message-history">
      {messages.map((msg, index) => (
        msg.sender === 'gemini' 
          ? <GeminiMessage key={index} text={msg.text} />
          : <UserMessage key={index} text={msg.text} />
      ))}
    </div>
  );
}

export default MessageHistory;

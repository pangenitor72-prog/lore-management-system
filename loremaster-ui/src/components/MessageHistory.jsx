import React from 'react';

const MessageHistory = () => {
  return (
    <div className="message-history">
      {/* Example messages */}
      <div className="gemini-message">
        <span className="avatar">📜</span>
        <div className="message-content">Welcome, Jim. How can I assist with your lore?</div>
      </div>
      <div className="user-message">
        <span className="avatar">✍️</span>
        <div className="message-content">Show me all entities.</div>
      </div>
    </div>
  );
};

export default MessageHistory;

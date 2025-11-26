import React from 'react';

function GeminiMessage({ text, avatar = '🗡️' }) { // Using emoji as placeholder avatar
  return (
    <div className="message gemini">
      <span className="avatar">{avatar}</span>
      <p>{text}</p>
    </div>
  );
}

export default GeminiMessage;

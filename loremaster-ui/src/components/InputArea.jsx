import React from 'react';

const InputArea = () => {
  return (
    <div className="input-area">
      <input type="text" placeholder="Ask me anything about your lore..." />
      <button className="send-button">Send</button>
    </div>
  );
};

export default InputArea;

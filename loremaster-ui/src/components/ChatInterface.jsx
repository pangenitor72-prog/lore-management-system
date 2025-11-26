import React from 'react';
import MessageHistory from './MessageHistory';
import InputArea from './InputArea';

const ChatInterface = () => {
  return (
    <div className="chat-interface">
      <MessageHistory />
      <InputArea />
    </div>
  );
};

export default ChatInterface;

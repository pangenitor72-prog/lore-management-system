import React from 'react';
import MessageHistory from './MessageHistory';
import InputArea from './InputArea';

function ChatInterface({ messages, onSendMessage }) {
  return (
    <div className="chat-interface">
      <MessageHistory messages={messages} />
      <InputArea onSendMessage={onSendMessage} />
    </div>
  );
}

export default ChatInterface;

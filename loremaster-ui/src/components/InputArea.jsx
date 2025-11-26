import React, { useState } from 'react';
import TextInput from './TextInput';
import SendButton from './SendButton';

function InputArea({ onSendMessage }) {
  const [inputText, setInputText] = useState('');

  const handleSubmit = () => {
    if (inputText.trim()) {
      onSendMessage(inputText);
      setInputText('');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSubmit();
    }
  };

  return (
    <div className="input-area">
      <TextInput 
        value={inputText}
        onChange={setInputText}
        onKeyPress={handleKeyPress}
        placeholder="Ask me anything about your lore..."
      />
      <SendButton onClick={handleSubmit} />
    </div>
  );
}

export default InputArea;

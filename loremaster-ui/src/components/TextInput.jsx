import React from 'react';

function TextInput({ value, onChange, onKeyPress, placeholder }) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyPress={onKeyPress}
      placeholder={placeholder}
    />
  );
}

export default TextInput;

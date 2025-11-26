import React from 'react';

function UserMessage({ text, avatar = '📜' }) { // Using emoji as placeholder avatar
  return (
    <div className="message user">
      <p>{text}</p>
      <span className="avatar">{avatar}</span>
    </div>
  );
}

export default UserMessage;

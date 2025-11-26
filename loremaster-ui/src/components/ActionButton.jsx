import React from 'react';

function ActionButton({ id, label, icon, onClick, disabled, tooltip }) {
  return (
    <button
      id={id}
      className="button-primary quick-action-button"
      onClick={onClick}
      disabled={disabled}
      title={tooltip || label}
    >
      {icon && <span className="icon">{icon}</span>}
      {label && <span className="label">{label}</span>}
    </button>
  );
}

export default ActionButton;

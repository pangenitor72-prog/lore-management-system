import React from 'react';

function UndoButton({ disabled, onClick, tooltip }) {
  return (
    <button
      className="button-primary"
      onClick={onClick}
      disabled={disabled}
      title={tooltip} // Tooltip for hover
    >
      ↶ Undo
    </button>
  );
}

export default UndoButton;

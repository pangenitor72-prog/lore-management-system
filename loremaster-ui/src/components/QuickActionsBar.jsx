import React from 'react';
import UndoButton from './UndoButton';
import ActionButton from './ActionButton';

function QuickActionsBar({ canUndo, actions, onActionClick }) {
  const getQuickActions = (currentActions) => {
    const defaultActions = [
      { id: 'undo', label: 'Undo', icon: '↶', visible: 'always', disabled: !canUndo }
    ];
    
    // Combine default actions with context-specific actions, ensuring undo is first
    const contextActions = currentActions.filter(action => action.id !== 'undo');
    return [...defaultActions, ...contextActions];
  };

  return (
    <div className="quick-actions-bar">
      {getQuickActions(actions).map(action => (
        <ActionButton
          key={action.id}
          id={action.id}
          label={action.label}
          icon={action.icon}
          onClick={() => onActionClick(action.id)}
          disabled={action.disabled}
          tooltip={action.label}
        />
      ))}
    </div>
  );
}

export default QuickActionsBar;

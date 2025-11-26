import React from 'react';

function CanonDecisionContext({ data }) {
  return (
    <div className="context-placeholder canon-decision-context">
      <h2>Canon Decision Context</h2>
      <p>Data: {JSON.stringify(data)}</p>
    </div>
  );
}

export default CanonDecisionContext;

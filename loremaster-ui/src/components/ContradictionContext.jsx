import React from 'react';

function ContradictionContext({ data }) {
  return (
    <div className="context-placeholder contradiction-context">
      <h2>Contradiction Context</h2>
      <p>Data: {JSON.stringify(data)}</p>
    </div>
  );
}

export default ContradictionContext;

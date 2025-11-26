import React from 'react';

function EntityDetailContext({ data }) {
  return (
    <div className="context-placeholder entity-detail-context">
      <h2>Entity Detail Context</h2>
      <p>Data: {JSON.stringify(data)}</p>
    </div>
  );
}

export default EntityDetailContext;

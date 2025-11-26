import React from 'react';

const EntityDetailContext = () => {
  return (
    <div className="entity-detail-context">
      <h2>Entity Details</h2>
      <div className="entity-header">
        <h3>[Entity Name]</h3>
        <p>[Type] - [Confidence] - [Party Knowledge]</p>
      </div>
      <div className="section">
        <h4>Aliases</h4>
        <p>No aliases.</p>
      </div>
      <div className="section">
        <h4>Description</h4>
        <p>No description.</p>
      </div>
      <div className="section">
        <h4>Related Entities</h4>
        <p>No related entities.</p>
      </div>
      <div className="section">
        <h4>Sources</h4>
        <p>No sources.</p>
      </div>
      <div className="actions">
        <button>Edit</button>
        <button>Set Knowledge</button>
      </div>
    </div>
  );
};

export default EntityDetailContext;

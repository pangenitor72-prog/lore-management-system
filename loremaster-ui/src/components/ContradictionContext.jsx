import React from 'react';

const ContradictionContext = () => {
  return (
    <div className="contradiction-context">
      <h2>Contradiction Review</h2>
      <div className="contradiction-card">
        <div className="header">
          <span className="type">[Contradiction Type]</span>
          <span className="severity-badge">[Severity]</span>
        </div>
        <p className="description">
          [Description of the contradiction]
        </p>

        <div className="version-comparison">
          <div className="version">
            <h4>Version A</h4>
            <p className="text">[Text of Version A]</p>
            <p className="metadata">Source: [Source A] | Confidence: [Confidence A]</p>
          </div>
          <div className="version">
            <h4>Version B</h4>
            <p className="text">[Text of Version B]</p>
            <p className="metadata">Source: [Source B] | Confidence: [Confidence B]</p>
          </div>
        </div>

        <div className="impact-preview">
          <button className="toggle-impact">
            Show Impact (0 entities affected)
          </button>
          <div className="affected-list">
            {/* Affected entities will be listed here */}
            <p>No entities affected previewed.</p>
          </div>
        </div>

        <div className="actions">
          <button className="button-primary">Make A Canon</button>
          <button className="button-primary">Make B Canon</button>
          <button>Skip</button>
          <button>Dismiss</button>
        </div>
      </div>
      <p className="navigation-hint">0 more contradictions after this</p>
    </div>
  );
};

export default ContradictionContext;

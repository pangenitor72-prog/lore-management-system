import React from 'react';

function DashboardContext({ data }) {
  return (
    <div className="context-placeholder dashboard-context">
      <h2>Dashboard Context</h2>
      <p>Data: {JSON.stringify(data)}</p>
    </div>
  );
}

export default DashboardContext;

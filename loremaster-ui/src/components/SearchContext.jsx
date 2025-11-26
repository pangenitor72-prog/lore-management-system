import React from 'react';

function SearchContext({ data }) {
  return (
    <div className="context-placeholder search-context">
      <h2>Search Context</h2>
      <p>Data: {JSON.stringify(data)}</p>
    </div>
  );
}

export default SearchContext;

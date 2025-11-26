import React from 'react';

const SearchContext = () => {
  return (
    <div className="search-context">
      <h2>Search Entities</h2>
      <div className="filter-bar">
        <p>Filters will go here</p>
      </div>
      <div className="results-header">
        <p>Found 0 entities</p>
      </div>
      <div className="results-grid">
        <p>Entity cards will be displayed here</p>
      </div>
      <div className="bulk-action-bar">
        <p>Bulk actions will go here</p>
      </div>
    </div>
  );
};

export default SearchContext;

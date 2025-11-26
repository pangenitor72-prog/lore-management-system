import React from 'react';

const UploadContext = () => {
  return (
    <div className="upload-context">
      <h2>Upload New Lore</h2>
      <div className="drop-zone">
        <p>Drop text files here or click to browse</p>
      </div>
      <div className="processing-queue">
        <h3>Processing Queue</h3>
        <p>No files in queue.</p>
      </div>
      <div className="results-summary">
        <h3>Results Summary</h3>
        <p>No batches processed.</p>
      </div>
    </div>
  );
};

export default UploadContext;

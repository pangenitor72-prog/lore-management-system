import React, { useState } from 'react';

function UploadContext({ data }) {
  const [files, setFiles] = useState([]);
  const [batchComplete, setBatchComplete] = useState(false);
  const [stats, setStats] = useState({
    filesProcessed: 0,
    entitiesFound: 0,
    contradictions: 0,
  });

  const handleFiles = (acceptedFiles) => {
    const newFiles = acceptedFiles.map(file => ({
      file,
      name: file.name,
      status: 'pending', // 'pending', 'processing', 'complete', 'error'
      progress: 0,
    }));
    setFiles(prevFiles => [...prevFiles, ...newFiles]);
    // TODO: Initiate upload process via WebSocket
    console.log("Files ready for upload:", newFiles);

    // Mock processing for demonstration
    setTimeout(() => {
      setFiles(prev => prev.map(f => ({ ...f, status: 'processing', progress: 50 })));
      setTimeout(() => {
        setFiles(prev => prev.map(f => ({ ...f, status: 'complete', progress: 100 })));
        setBatchComplete(true);
        setStats({
          filesProcessed: newFiles.length,
          entitiesFound: Math.floor(Math.random() * 50) + 10,
          contradictions: Math.floor(Math.random() * 5),
        });
      }, 2000);
    }, 1000);
  };

  const DropZone = ({ onDrop, onBrowse }) => {
    const handleDragOver = (e) => {
      e.preventDefault();
      e.stopPropagation();
    };

    const handleDrop = (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        onDrop(Array.from(e.dataTransfer.files));
      }
    };

    return (
      <div 
        className="drop-zone card" 
        onDragOver={handleDragOver} 
        onDrop={handleDrop}
        onClick={onBrowse}
      >
        <span className="icon">📜</span>
        <p>Drop text files here or click to browse</p>
        <input 
          type="file" 
          multiple 
          hidden 
          onChange={(e) => onDrop(Array.from(e.target.files))} 
        />
      </div>
    );
  };

  const ProcessingQueue = ({ visible, queueItems }) => {
    if (!visible) return null;
    return (
      <div className="processing-queue card">
        <h3>Processing Queue</h3>
        {queueItems.map((item, index) => (
          <QueueItem key={index} file={item} />
        ))}
      </div>
    );
  };

  const QueueItem = ({ file }) => (
    <div className="queue-item">
      <span className="file-name">{file.name}</span>
      <span className={`status ${file.status}`}>
        {file.status === 'processing' && '...'}
        {file.status === 'complete' && '✓'}
        {file.status === 'error' && '✗'}
        {file.status === 'pending' && '-'}
      </span>
    </div>
  );

  const ResultsSummary = ({ visible, stats, switchContext }) => {
    if (!visible) return null;
    return (
      <div className="results-summary card">
        <h3>Upload Summary</h3>
        <div className="stats-grid">
          <Stat number={stats.filesProcessed} label="Files Processed" />
          <Stat number={stats.entitiesFound} label="Entities Found" actionLabel="View All" onActionClick={() => switchContext('search')} />
          <Stat number={stats.contradictions} label="Contradictions Detected" warning={stats.contradictions > 0} actionLabel="Review" onActionClick={() => switchContext('contradiction')} />
        </div>
      </div>
    );
  };

  const Stat = ({ number, label, warning = false, actionLabel, onActionClick }) => (
    <div className={`stat-card ${warning ? 'warning' : ''}`}>
      <span className="number">{number}</span>
      <span className="label">{label}</span>
      {actionLabel && <button className="action-link" onClick={onActionClick}>{actionLabel}</button>}
    </div>
  );


  return (
    <div className="upload-context">
      <DropZone onDrop={handleFiles} onBrowse={() => { /* file input click */ }} />
      <ProcessingQueue visible={files.length > 0 && !batchComplete} queueItems={files.filter(f => f.status !== 'complete')} />
      <ResultsSummary 
        visible={batchComplete} 
        stats={stats} 
        switchContext={setCurrentContext} 
      />
    </div>
  );
}

export default UploadContext;
import { useEffect, useRef, useState } from 'react';
import { uploadPDF } from '../api/api';

const MAX_BYTES = 100 * 1024 * 1024;

function cleanError(err) {
  const msg = String(err);
  return msg.startsWith('Error: ') ? msg.slice(7) : msg;
}

const UploadIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
    <polyline points="17 8 12 3 7 8"/>
    <line x1="12" y1="3" x2="12" y2="15"/>
  </svg>
);

const IconPending = () => (
  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
    <circle cx="6" cy="6" r="3" fill="currentColor"/>
  </svg>
);

const IconUploading = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="17 8 12 3 7 8"/>
    <line x1="12" y1="3" x2="12" y2="18"/>
  </svg>
);

const IconDone = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
);

const IconError = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="18" y1="6" x2="6" y2="18"/>
    <line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);

const STATUS_ICONS = {
  pending:   <span className="upload-queue-icon upload-queue-icon-pending"><IconPending /></span>,
  uploading: <span className="upload-queue-icon upload-queue-icon-uploading"><IconUploading /></span>,
  done:      <span className="upload-queue-icon upload-queue-icon-done"><IconDone /></span>,
  error:     <span className="upload-queue-icon upload-queue-icon-error"><IconError /></span>,
};

export default function UploadSection({ onSuccess }) {
  const [queue, setQueue]         = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [inputKey, setInputKey]   = useState(0);
  const inputRef = useRef(null);

  const isUploading  = queue.some((item) => item.status === 'uploading');
  const isAllSettled = queue.length > 0 && queue.every((item) => item.status === 'done' || item.status === 'error');

  function handleFiles(fileList) {
    const items = Array.from(fileList).map((file) => {
      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
      if (!isPdf) {
        return { id: crypto.randomUUID(), file, status: 'error', progress: 0, msg: 'Not a PDF file' };
      }
      if (file.size > MAX_BYTES) {
        return { id: crypto.randomUUID(), file, status: 'error', progress: 0, msg: 'Exceeds the 100 MB limit' };
      }
      return { id: crypto.randomUUID(), file, status: 'pending', progress: 0, msg: null };
    });

    if (items.length > 0) {
      setQueue((q) => [...q, ...items]);
      setInputKey((k) => k + 1);
    }
  }

  useEffect(() => {
    if (isUploading) return;
    const nextIndex = queue.findIndex((item) => item.status === 'pending');
    if (nextIndex === -1) return;

    const { file } = queue[nextIndex];

    setQueue((q) => q.map((item, i) => i === nextIndex ? { ...item, status: 'uploading', progress: 0 } : item));

    uploadPDF(file, (p) => {
      setQueue((q) => q.map((item, i) => i === nextIndex ? { ...item, progress: p } : item));
    })
      .then(() => {
        setQueue((q) => q.map((item, i) => i === nextIndex ? { ...item, status: 'done', progress: 1 } : item));
        onSuccess?.();
      })
      .catch((err) => {
        setQueue((q) => q.map((item, i) => i === nextIndex ? { ...item, status: 'error', msg: cleanError(err) } : item));
      });
  }, [queue]);

  function handleDragEnter(e) { e.preventDefault(); setIsDragging(true); }
  function handleDragOver(e)  { e.preventDefault(); setIsDragging(true); }
  function handleDragLeave(e) { if (!e.currentTarget.contains(e.relatedTarget)) setIsDragging(false); }
  function handleDrop(e) {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  }

  return (
    <div
      className={`upload-area${isDragging ? ' is-dragging' : ''}`}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input
        key={inputKey}
        ref={inputRef}
        type="file"
        accept=".pdf"
        multiple
        aria-label="Choose PDF files to upload"
        style={{ display: 'none' }}
        onChange={(e) => handleFiles(e.target.files)}
      />
      <button
        className="upload-doc-btn"
        disabled={isUploading}
        onClick={() => inputRef.current?.click()}
      >
        <UploadIcon />
        {isUploading ? 'Uploading…' : 'Upload Document'}
      </button>

      {queue.length === 0 && (
        <p className="upload-hint">or drop PDFs here</p>
      )}

      {queue.length > 0 && (
        <ul className="upload-queue" aria-label="Upload queue">
          {queue.map((item) => (
            <li key={item.id} className="upload-queue-item">
              <div className="upload-queue-row">
                {STATUS_ICONS[item.status]}
                <span className="upload-queue-name" title={item.file.name}>{item.file.name}</span>
              </div>
              {item.status === 'uploading' && (
                <div className="upload-queue-bar" role="progressbar" aria-valuenow={Math.round(item.progress * 100)} aria-valuemin={0} aria-valuemax={100}>
                  <div className="upload-queue-bar-fill" style={{ width: `${item.progress * 100}%` }} />
                </div>
              )}
              {item.status === 'error' && (
                <p className="upload-queue-err">{item.msg}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {isAllSettled && (
        <button className="upload-clear-btn" onClick={() => setQueue([])}>
          Clear
        </button>
      )}
    </div>
  );
}

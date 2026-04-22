import { useEffect, useState } from 'react';
import { deleteDocument, listDocuments } from '../api/api';

const FileIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
  </svg>
);

const TrashIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
    <path d="M10 11v6"/><path d="M14 11v6"/>
    <path d="M9 6V4h6v2"/>
  </svg>
);

export default function DocumentsSection() {
  const [docs, setDocs]   = useState([]);
  const [error, setError] = useState(null);

  async function load() {
    try { setError(null); setDocs(await listDocuments()); }
    catch (e) { setError(String(e)); }
  }

  useEffect(() => { load(); }, []);

  async function handleDelete(filename) {
    try { await deleteDocument(filename); setDocs((prev) => prev.filter((d) => d.filename !== filename)); }
    catch (e) { setError(String(e)); }
  }

  return (
    <div className="kb-section">
      <p className="kb-label">Knowledge Base</p>
      {error && <p className="upload-err">{error}</p>}
      {docs.length === 0 && !error && <p className="kb-empty">No documents yet.</p>}
      <ul className="kb-list">
        {docs.map((doc) => (
          <li key={doc.filename} className="kb-item">
            <span className="kb-icon"><FileIcon /></span>
            <span className="kb-name" title={doc.filename}>{doc.filename}</span>
            <button className="kb-delete" onClick={() => handleDelete(doc.filename)} title="Delete">
              <TrashIcon />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

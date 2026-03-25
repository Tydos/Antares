import { useState, useEffect } from 'react';
import { listDocuments, deleteDocument } from '../api/api';

export default function DocumentsSection() {
  const [docs, setDocs] = useState([]);
  const [error, setError] = useState(null);

  async function load() {
    try { setDocs(await listDocuments()); }
    catch (e) { setError(String(e)); }
  }

  useEffect(() => { load(); }, []);

  async function handleDelete(filename) {
    try {
      await deleteDocument(filename);
      setDocs((prev) => prev.filter((d) => d.filename !== filename));
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <section>
      <div className="row" style={{ marginBottom: 12 }}>
        <h2 style={{ marginBottom: 0 }}>Documents</h2>
        <button onClick={load}>Refresh</button>
      </div>

      {error && <p className="error">{error}</p>}
      {docs.length === 0 && <p className="muted">No documents indexed yet.</p>}

      {docs.map((doc) => (
        <div key={doc.filename} className="doc-row">
          <span className="doc-name">{doc.filename}</span>
          <span className="muted">{doc.page_count} pages</span>
          <span className="muted">{doc.uploaded_at.slice(0, 10)}</span>
          <button className="danger" onClick={() => handleDelete(doc.filename)}>Delete</button>
        </div>
      ))}
    </section>
  );
}

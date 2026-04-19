import { useState, useEffect } from 'react';
import { listDocuments, deleteDocument } from '../api/api';

const STATUS_LABEL = {
  pending: 'Indexing…',
  indexed: 'Indexed',
  skipped: 'No text extracted',
  failed: 'Indexing failed',
};

function formatDate(iso) {
  if (!iso || typeof iso !== 'string') return '—';
  return iso.slice(0, 10);
}

function statusLabel(status) {
  if (!status) return '—';
  return STATUS_LABEL[status] ?? status;
}

export default function DocumentsSection() {
  const [docs, setDocs] = useState([]);
  const [error, setError] = useState(null);

  async function load() {
    try {
      setError(null);
      setDocs(await listDocuments());
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

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
        <button type="button" onClick={load}>
          Refresh
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {docs.length === 0 && <p className="muted">No uploads yet.</p>}

      {docs.map((doc) => (
        <div key={doc.filename} className="doc-row">
          <span className="doc-name" title={doc.filename}>
            {doc.filename}
          </span>
          <span className="muted" title="Indexing / search status">
            {statusLabel(doc.status)}
          </span>
          <span className="muted">{doc.page_count ?? 0} pages</span>
          <span className="muted">{formatDate(doc.uploaded_at)}</span>
          {doc.blob_url ? (
            <a
              className="muted"
              href={doc.blob_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Blob
            </a>
          ) : null}
          <button type="button" className="danger" onClick={() => handleDelete(doc.filename)}>
            Delete
          </button>
        </div>
      ))}
    </section>
  );
}

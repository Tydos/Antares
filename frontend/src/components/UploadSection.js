import { useRef, useState } from 'react';
import { uploadPDF } from '../api/api';

export default function UploadSection() {
  const [key, setKey]           = useState(0);
  const [loading, setLoading]   = useState(false);
  const [progress, setProgress] = useState(null);
  const [msg, setMsg]           = useState(null);
  const inputRef = useRef(null);

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setMsg(null);
    setLoading(true);
    setProgress(0);
    try {
      await uploadPDF(file, setProgress);
      setMsg({ ok: true, text: 'Indexing in progress…' });
    } catch (err) {
      setMsg({ ok: false, text: String(err) });
    } finally {
      setLoading(false);
      setProgress(null);
      setKey((k) => k + 1);
    }
  }

  return (
    <div className="upload-area">
      <input key={key} ref={inputRef} type="file" accept=".pdf"
        style={{ display: 'none' }} onChange={handleFile} />
      <button
        className="upload-doc-btn"
        disabled={loading}
        onClick={() => { setMsg(null); inputRef.current?.click(); }}
      >
        <span className="upload-plus">+</span>
        {loading ? 'Uploading…' : 'Upload Document'}
      </button>
      {loading && progress !== null && (
        <div className="progress-bar"><div className="progress-fill" style={{ width: `${Math.round(progress * 100)}%` }} /></div>
      )}
      {msg && <p className={msg.ok ? 'upload-ok' : 'upload-err'}>{msg.text}</p>}
    </div>
  );
}

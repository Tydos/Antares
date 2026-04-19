import { useState } from 'react';
import { uploadPDF } from '../api/api';

export default function UploadSection() {
  const [key, setKey] = useState(0);
  const [file, setFile] = useState(null);
  const [msg, setMsg] = useState(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(null);

  async function handleUpload() {
    setLoading(true);
    setMsg(null);
    setProgress(0);
    try {
      const res = await uploadPDF(file, setProgress);
      setMsg({ ok: true, text: res.status });
      setFile(null);
      setKey((k) => k + 1);
    } catch (e) {
      setMsg({ ok: false, text: String(e) });
    } finally {
      setLoading(false);
      setProgress(null);
    }
  }

  return (
    <section>
      <h2>Upload PDF</h2>
      <div className="row">
        <input key={key} type="file" accept=".pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <button className="primary" disabled={!file || loading} onClick={handleUpload}>
          {loading ? 'Uploading…' : 'Upload'}
        </button>
      </div>
      {loading && progress !== null && <progress value={progress} max={1} />}
      {msg && <p className={msg.ok ? 'success' : 'error'}>{msg.text}</p>}
    </section>
  );
}

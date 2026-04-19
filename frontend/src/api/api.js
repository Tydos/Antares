import { upload } from '@vercel/blob/client';

async function request(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail ?? j.error ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return res.json();
}

const notifyUploadComplete = (filename, blobUrl) =>
  request('/upload-complete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, blobUrl }),
  });

/** Same-origin paths; local CRA proxy → FastAPI. On Vercel, vercel.json rewrites these to /_/backend/... */
const BLOB_HANDLE_UPLOAD = '/blob-upload';

export const uploadPDF = async (file, onProgress) => {
  const result = await upload(file.name, file, {
    access: 'public',
    handleUploadUrl: BLOB_HANDLE_UPLOAD,
    contentType: file.type || 'application/pdf',
    onUploadProgress: onProgress
      ? ({ loaded, total }) => {
          if (total > 0) onProgress(loaded / total);
        }
      : undefined,
  });
  return notifyUploadComplete(result.pathname, result.url);
};

export const search = (query, topK = 5) =>
  request(`/search?q=${encodeURIComponent(query)}&top_k=${topK}`).then((d) => d.results);

export const listDocuments = () =>
  request('/documents').then((d) => d.documents);

export const deleteDocument = (filename) =>
  request(`/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });

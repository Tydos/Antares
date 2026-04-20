import { upload } from '@vercel/blob/client';

/**
 * Same-origin paths; local CRA proxy -> FastAPI.
 * On Vercel, vercel.json rewrites these to /_/backend/...
 */

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

const postJSON = (url, body) =>
  request(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const uploadPDF = async (file, onProgress) => {
  const result = await upload(file.name, file, {
    access: 'public',
    handleUploadUrl: '/blob-upload',
    contentType: file.type || 'application/pdf',
    onUploadProgress: onProgress
      ? ({ loaded, total }) => {
          if (total > 0) onProgress(loaded / total);
        }
      : undefined,
  });
  return postJSON('/upload-complete', { filename: result.pathname, blobUrl: result.url });
};

export const listDocuments = () =>
  request('/documents').then((d) => d.documents);

export const deleteDocument = (filename) =>
  request(`/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });

export const query = (question, { topK = 5, filenames } = {}) =>
  postJSON('/query', {
    question,
    top_k: topK,
    ...(filenames && filenames.length ? { filenames } : {}),
  });

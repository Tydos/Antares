import { upload } from '@vercel/blob/client';

const API = process.env.REACT_APP_API_PREFIX || '';

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
    handleUploadUrl: `${API}/request_upload_token`,
    contentType: file.type || 'application/pdf',
    onUploadProgress: onProgress
      ? ({ loaded, total }) => {
          if (total > 0) onProgress(loaded / total);
        }
      : undefined,
  });
  return postJSON(`${API}/upload-complete`, { filename: result.pathname, blobUrl: result.url });
};

export const listDocuments = () =>
  request(`${API}/documents`).then((d) => d.documents);

export const deleteDocument = (filename) =>
  request(`${API}/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });

export const query = (question, { topK = 5, filenames } = {}) =>
  postJSON(`${API}/query`, {
    question,
    top_k: topK,
    ...(filenames && filenames.length ? { filenames } : {}),
  });

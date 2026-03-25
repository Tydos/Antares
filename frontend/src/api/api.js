async function request(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

export const uploadPDF = (file) => {
  const form = new FormData();
  form.append('file', file);
  return request('/upload', { method: 'POST', body: form });
};

export const search = (query, topK = 5) =>
  request(`/search?q=${encodeURIComponent(query)}&top_k=${topK}`).then((d) => d.results);

export const listDocuments = () =>
  request('/documents').then((d) => d.documents);

export const deleteDocument = (filename) =>
  request(`/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });

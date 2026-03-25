import { useState } from 'react';
import { search } from '../api/api';

export default function SearchSection() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSearch() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResults(await search(query.trim()));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h2>Search</h2>
      <div className="row">
        <input
          type="text"
          style={{ flex: 1 }}
          placeholder="Enter query…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        />
        <button className="primary" disabled={loading || !query.trim()} onClick={handleSearch}>
          {loading ? '…' : 'Search'}
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {results !== null && results.length === 0 && (
        <p className="muted" style={{ marginTop: 12 }}>No results.</p>
      )}

      <div style={{ marginTop: 12 }}>
        {(results ?? []).map((hit, i) => (
          <div key={i} className="result">
            <strong>{hit.filename}</strong>
            <span className="result-meta"> · page {hit.page_number} · score {hit.score.toFixed(2)}</span>
            <p className="result-content">
              {hit.highlights?.length
                ? hit.highlights.map((f) => f.replace(/<[^>]+>/g, '')).join(' … ')
                : hit.content.slice(0, 400)}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

import { useEffect, useState } from 'react';
import { listDocuments, query } from '../api/api';

const MODES = [
  { value: 'hybrid',   label: 'Hybrid',   title: 'Vector + keyword, fused with RRF' },
  { value: 'semantic', label: 'Semantic',  title: 'Vector cosine similarity only' },
  { value: 'keyword',  label: 'Keyword',   title: 'Full-text search only (ts_rank)' },
];

export default function ChatSection() {
  const [question, setQuestion]     = useState('');
  const [searchMode, setSearchMode] = useState('hybrid');
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState(null);
  const [result, setResult]         = useState(null);
  const [blobByFilename, setBlobByFilename] = useState({});

  useEffect(() => {
    listDocuments()
      .then((docs) =>
        setBlobByFilename(Object.fromEntries(docs.map((d) => [d.filename, d.blob_url || ''])))
      )
      .catch(() => {});
  }, []);

  async function handleAsk(e) {
    e?.preventDefault?.();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await query(question.trim(), { searchMode }));
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  const answer = result?.answer;
  const chunks = result?.chunks ?? [];
  const latency = result?.latency;
  const hrefFor = (c) => {
    const url = blobByFilename[c.filename];
    return url ? `${url}#page=${c.page}` : null;
  };

  return (
    <section>
      <h2>Ask</h2>

      <div className="mode-toggle" role="group" aria-label="Search mode">
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            title={m.title}
            className={searchMode === m.value ? 'active' : ''}
            onClick={() => setSearchMode(m.value)}
          >
            {m.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleAsk} className="row" style={{ marginTop: 10 }}>
        <input
          className="ask-input"
          type="text"
          placeholder="Ask a question about your PDFs…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button className="primary" type="submit" disabled={!question.trim() || loading}>
          {loading ? 'Searching…' : 'Ask'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {answer && (
        <div className="answer-card">
          <div className="answer-label">Answer</div>
          {answer}
        </div>
      )}

      {latency && (
        <p className="muted latency-bar">
          embed {latency.embed}ms · search {latency.search}ms · llm {latency.llm}ms · total {latency.total}ms
        </p>
      )}

      {result && chunks.length === 0 && <p className="muted ask-empty">No matches found.</p>}

      {chunks.length > 0 && (
        <div className="ask-results">
          {chunks.map((c, i) => {
            const href = hrefFor(c);
            return (
              <div key={i} className="chunk-card">
                <div className="chunk-meta">
                  {href ? (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {c.filename} · p.{c.page}
                    </a>
                  ) : (
                    <span>{c.filename} · p.{c.page}</span>
                  )}
                  <span className="muted">score {c.score.toFixed(4)}</span>
                </div>
                <p className="chunk-text">{c.content}</p>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

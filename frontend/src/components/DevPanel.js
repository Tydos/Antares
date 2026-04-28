import { useState } from 'react';

const ChevronIcon = ({ open }) => (
  <svg
    width="11" height="11" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="2.5"
    strokeLinecap="round" strokeLinejoin="round"
    className={`dp-chevron${open ? ' open' : ''}`}
    aria-hidden="true"
  >
    <polyline points="6 9 12 15 18 9"/>
  </svg>
);

function LatencyBar({ latency }) {
  if (!latency) return <p className="dp-empty">No data.</p>;
  const fields = [
    { key: 'embed',  label: 'Embed' },
    { key: 'search', label: 'Search' },
    { key: 'llm',    label: 'LLM' },
    { key: 'total',  label: 'Total' },
  ];
  const max = latency.total || 1;
  return (
    <div className="dp-latency">
      {fields.map(({ key, label }) =>
        latency[key] != null ? (
          <div key={key} className="dp-latency-row">
            <span className="dp-latency-label">{label}</span>
            <div
              className="dp-latency-track"
              role="meter"
              aria-label={`${label} latency`}
              aria-valuenow={Math.round(latency[key])}
              aria-valuemin={0}
              aria-valuemax={Math.round(max)}
            >
              <div className="dp-latency-fill" style={{ width: `${Math.min(100, (latency[key] / max) * 100)}%` }} />
            </div>
            <span className="dp-latency-ms">{Math.round(latency[key])}ms</span>
          </div>
        ) : null
      )}
    </div>
  );
}

function ChunkRow({ chunk, i }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="dp-chunk">
      <button
        className="dp-chunk-header"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="dp-chunk-left">
          <span className="dp-chunk-num">{i + 1}</span>
          <span className="dp-chunk-file" title={chunk.filename}>{chunk.filename} · p.{chunk.page}</span>
        </span>
        <span className="dp-chunk-right">
          <span className="dp-score">{typeof chunk.score === 'number' ? chunk.score.toFixed(5) : chunk.score}</span>
          <ChevronIcon open={open} />
        </span>
      </button>
      {open && <pre className="dp-chunk-body">{chunk.content}</pre>}
    </div>
  );
}

export default function DevPanel({ messages }) {
  const assistantMsgs = messages.filter((m) => m.role === 'assistant');
  const latest = assistantMsgs[assistantMsgs.length - 1] ?? null;

  const avgLlm   = assistantMsgs.length ? Math.round(assistantMsgs.reduce((s, m) => s + (m.latency?.llm   ?? 0), 0) / assistantMsgs.length) : null;
  const avgTotal = assistantMsgs.length ? Math.round(assistantMsgs.reduce((s, m) => s + (m.latency?.total ?? 0), 0) / assistantMsgs.length) : null;

  return (
    <aside className="dev-right-panel" aria-label="Retrieval inspector">
      <div className="dp-header">
        <span className="dp-title">Inspector</span>
      </div>

      <div className="dp-section">
        <p className="dp-section-label">Session</p>
        <div className="dp-stats-grid">
          <div className="dp-stat"><span className="dp-stat-val">{messages.length}</span><span className="dp-stat-key">messages</span></div>
          <div className="dp-stat"><span className="dp-stat-val">{assistantMsgs.length}</span><span className="dp-stat-key">responses</span></div>
          <div className="dp-stat"><span className="dp-stat-val">{avgLlm != null ? `${avgLlm}ms` : '—'}</span><span className="dp-stat-key">avg llm</span></div>
          <div className="dp-stat"><span className="dp-stat-val">{avgTotal != null ? `${avgTotal}ms` : '—'}</span><span className="dp-stat-key">avg total</span></div>
        </div>
      </div>

      {latest ? (
        <>
          <div className="dp-section">
            <p className="dp-section-label">Latency · latest</p>
            <LatencyBar latency={latest.latency} />
          </div>
          <div className="dp-section dp-section-last">
            <p className="dp-section-label">Chunks ({latest.chunks?.length ?? 0})</p>
            {latest.chunks?.length > 0
              ? latest.chunks.map((c, i) => <ChunkRow key={i} chunk={c} i={i} />)
              : <p className="dp-empty">No chunks retrieved.</p>
            }
          </div>
        </>
      ) : (
        <div className="dp-placeholder">
          <p>Send a message to inspect retrieval and latency.</p>
        </div>
      )}
    </aside>
  );
}

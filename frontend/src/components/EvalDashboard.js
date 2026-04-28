import { useEffect, useState } from 'react';
import { getEvalSummary } from '../api/api';

const MODES = ['hybrid', 'semantic', 'keyword'];

const ChevronIcon = ({ open }) => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={`eval-chevron${open ? ' open' : ''}`} aria-hidden="true">
    <polyline points="6 9 12 15 18 9"/>
  </svg>
);

function scoreClass(val) {
  if (val == null) return '';
  if (val >= 0.7) return 'score-good';
  if (val >= 0.4) return 'score-warn';
  return 'score-bad';
}

function hallClass(val) {
  if (val == null) return '';
  if (val < 0.2) return 'score-good';
  if (val <= 0.5) return 'score-warn';
  return 'score-bad';
}

function pct(v) {
  return v != null ? `${(v * 100).toFixed(1)}%` : '—';
}

function ms(v) {
  return v != null ? `${v}ms` : '—';
}

function LatencyRow({ label, value, max }) {
  if (value == null) return null;
  return (
    <div className="sess-latency-row">
      <span className="sess-latency-label">{label}</span>
      <div className="sess-latency-track" role="meter" aria-label={`${label} latency`} aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
        <div className="sess-latency-fill" style={{ width: `${Math.min(100, (value / (max || 1)) * 100)}%` }} />
      </div>
      <span className="sess-latency-ms">{value}ms</span>
    </div>
  );
}

function ChunkRow({ chunk, i }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="sess-chunk">
      <button className="sess-chunk-header" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="sess-chunk-left">
          <span className="sess-chunk-num">{i + 1}</span>
          <span className="sess-chunk-file" title={chunk.filename}>{chunk.filename} · p.{chunk.page}</span>
        </span>
        <span className="sess-chunk-right">
          <span className="sess-chunk-score">{typeof chunk.score === 'number' ? chunk.score.toFixed(5) : chunk.score}</span>
          <ChevronIcon open={open} />
        </span>
      </button>
      {open && <pre className="sess-chunk-body">{chunk.content}</pre>}
    </div>
  );
}

function SessionSection({ messages }) {
  const userMsgs      = messages.filter((m) => m.role === 'user');
  const assistantMsgs = messages.filter((m) => m.role === 'assistant');
  const msgsWithLat   = assistantMsgs.filter((m) => m.latency);
  const latest        = assistantMsgs[assistantMsgs.length - 1] ?? null;

  const avgOf = (key) => {
    const vals = msgsWithLat.map((m) => m.latency[key]).filter((v) => v != null);
    return vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null;
  };

  const avgEmbed  = avgOf('embed');
  const avgSearch = avgOf('search');
  const avgLlm    = avgOf('llm');
  const avgTotal  = avgOf('total');

  const latMax = latest?.latency?.total || 1;

  return (
    <section className="eval-section">
      <h2 className="eval-section-title">Session</h2>

      {messages.length === 0 ? (
        <p className="eval-empty">No session data yet — go to Chat and send a query.</p>
      ) : (
        <>
          <div className="sess-stats-grid">
            <div className="sess-stat"><span className="sess-stat-val">{userMsgs.length}</span><span className="sess-stat-key">Queries</span></div>
            <div className="sess-stat"><span className="sess-stat-val">{assistantMsgs.length}</span><span className="sess-stat-key">Responses</span></div>
            <div className="sess-stat"><span className="sess-stat-val">{ms(avgEmbed)}</span><span className="sess-stat-key">Avg embed</span></div>
            <div className="sess-stat"><span className="sess-stat-val">{ms(avgSearch)}</span><span className="sess-stat-key">Avg search</span></div>
            <div className="sess-stat"><span className="sess-stat-val">{ms(avgLlm)}</span><span className="sess-stat-key">Avg LLM</span></div>
            <div className="sess-stat"><span className="sess-stat-val">{ms(avgTotal)}</span><span className="sess-stat-key">Avg total</span></div>
          </div>

          {latest?.latency && (
            <div className="sess-card">
              <p className="sess-card-title">Latest response latency</p>
              <div className="sess-latency">
                <LatencyRow label="Embed"  value={latest.latency.embed}  max={latMax} />
                <LatencyRow label="Search" value={latest.latency.search} max={latMax} />
                <LatencyRow label="LLM"    value={latest.latency.llm}    max={latMax} />
                <LatencyRow label="Total"  value={latest.latency.total}  max={latMax} />
              </div>
            </div>
          )}

          {latest?.chunks?.length > 0 && (
            <div className="sess-card">
              <p className="sess-card-title">Latest retrieved chunks ({latest.chunks.length})</p>
              <div className="sess-chunks">
                {latest.chunks.map((c, i) => <ChunkRow key={i} chunk={c} i={i} />)}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

export default function EvalDashboard({ messages = [] }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getEvalSummary()
      .then(setData)
      .catch((e) => setError(String(e).replace(/^Error:\s*/, '')))
      .finally(() => setLoading(false));
  }, []);

  const ret = data?.retrieval;
  const aq  = data?.answer_quality;

  const bestPrecision = ret ? Math.max(...MODES.map((m) => ret[m]?.precision ?? -1)) : null;
  const bestRecall    = ret ? Math.max(...MODES.map((m) => ret[m]?.recall    ?? -1)) : null;
  const bestF1        = ret ? Math.max(...MODES.map((m) => ret[m]?.f1        ?? -1)) : null;

  return (
    <div className="eval-dashboard">

      <SessionSection messages={messages} />

      <section className="eval-section">
        <h2 className="eval-section-title">Retrieval Accuracy</h2>
        {loading ? (
          <p className="eval-empty">Loading…</p>
        ) : error ? (
          <p className="eval-error-inline">{error}</p>
        ) : ret ? (
          <table className="eval-table">
            <thead>
              <tr>
                <th>Mode</th>
                <th>Precision@5</th>
                <th>Recall@5</th>
                <th>F1</th>
                <th>N</th>
              </tr>
            </thead>
            <tbody>
              {MODES.map((mode) => {
                const r = ret[mode];
                if (!r) return null;
                return (
                  <tr key={mode}>
                    <td className="eval-mode-cell">{mode}</td>
                    <td className={r.precision === bestPrecision ? 'eval-best' : ''}>{pct(r.precision)}</td>
                    <td className={r.recall    === bestRecall    ? 'eval-best' : ''}>{pct(r.recall)}</td>
                    <td className={r.f1        === bestF1        ? 'eval-best' : ''}>{pct(r.f1)}</td>
                    <td className="eval-n">{r.n ?? '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="eval-empty">No retrieval data — run <code>evaluate.py</code> to generate results.</p>
        )}
      </section>

      <section className="eval-section">
        <h2 className="eval-section-title">Answer Quality</h2>
        {loading ? (
          <p className="eval-empty">Loading…</p>
        ) : error ? null : aq ? (
          <div className="eval-cards">
            {MODES.map((mode) => {
              const q = aq[mode];
              if (!q) return null;
              return (
                <div key={mode} className="eval-card">
                  <p className="eval-card-mode">{mode}</p>
                  <div className="eval-card-metrics">
                    <div className="eval-metric">
                      <span className={`eval-metric-val ${scoreClass(q.avg_faithfulness)}`}>{pct(q.avg_faithfulness)}</span>
                      <span className="eval-metric-label">Faithfulness</span>
                    </div>
                    <div className="eval-metric">
                      <span className={`eval-metric-val ${scoreClass(q.avg_relevance)}`}>{pct(q.avg_relevance)}</span>
                      <span className="eval-metric-label">Relevance</span>
                    </div>
                    <div className="eval-metric">
                      <span className={`eval-metric-val ${hallClass(q.hallucination_rate)}`}>{pct(q.hallucination_rate)}</span>
                      <span className="eval-metric-label">Hallucination</span>
                    </div>
                    <div className="eval-metric">
                      <span className="eval-metric-val">{q.n ?? '—'}</span>
                      <span className="eval-metric-label">Samples</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="eval-empty">No answer quality data — run <code>answer_quality.py</code> to generate results.</p>
        )}
      </section>

    </div>
  );
}

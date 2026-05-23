import { useEffect, useRef, useState } from 'react';
import { deletePackage, ingestPackage, listPackages, queryAdvisories } from '../api/api';

const ECOSYSTEMS = ['PyPI', 'npm', 'Go', 'crates.io', 'Maven', 'RubyGems'];

const STARTER_QUESTIONS = [
  'What CVEs affect this package?',
  'What is the minimum safe version?',
  'Are there any RCE vulnerabilities?',
  'Are there workarounds without upgrading?',
];

const SendIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);

const TrashIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
    <path d="M10 11v6"/><path d="M14 11v6"/>
    <path d="M9 6V4h6v2"/>
  </svg>
);

const ArrowIcon = () => (
  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="7" y1="17" x2="17" y2="7"/>
    <polyline points="7 7 17 7 17 17"/>
  </svg>
);

const STATUS_LABELS = { pending: 'Indexing…', failed: 'Failed', indexed: null };

function PackageStatus({ status }) {
  const label = STATUS_LABELS[status] ?? status;
  if (!label) return null;
  return <span className={`kb-status kb-status-${status}`}>{label}</span>;
}

export default function CybersecSection() {
  const [packages, setPackages]     = useState([]);
  const [pkgName, setPkgName]       = useState('');
  const [ecosystem, setEcosystem]   = useState('PyPI');
  const [ingesting, setIngesting]   = useState(false);
  const [pkgError, setPkgError]     = useState(null);

  const [messages, setMessages]     = useState([]);
  const [input, setInput]           = useState('');
  const [loading, setLoading]       = useState(false);
  const [chatError, setChatError]   = useState(null);
  const [searchMode, setSearchMode] = useState('hybrid');
  const threadRef                   = useRef(null);

  const MODES = [
    { value: 'hybrid',   label: 'Hybrid' },
    { value: 'semantic', label: 'Semantic' },
    { value: 'keyword',  label: 'Keyword' },
  ];

  async function loadPackages() {
    try {
      setPackages(await listPackages());
    } catch {
      /* non-fatal */
    }
  }

  useEffect(() => { loadPackages(); }, []);

  // Poll while any package is pending
  useEffect(() => {
    if (!packages.some((p) => p.status === 'pending')) return;
    const id = setInterval(loadPackages, 3000);
    return () => clearInterval(id);
  }, [packages]);

  useEffect(() => {
    if (threadRef.current) threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages, loading]);

  async function handleIngest(e) {
    e.preventDefault();
    const name = pkgName.trim();
    if (!name || ingesting) return;
    setPkgError(null);
    setIngesting(true);
    try {
      await ingestPackage(name, ecosystem);
      setPkgName('');
      // Optimistically add pending entry then reload
      setPackages((prev) => [
        { name, ecosystem, status: 'pending', advisory_count: 0, last_ingested: null },
        ...prev.filter((p) => !(p.name === name && p.ecosystem === ecosystem)),
      ]);
    } catch (err) {
      setPkgError(String(err).replace(/^Error:\s*/, ''));
    } finally {
      setIngesting(false);
    }
  }

  async function handleDelete(pkg) {
    try {
      await deletePackage(pkg.name, pkg.ecosystem);
      setPackages((prev) => prev.filter((p) => !(p.name === pkg.name && p.ecosystem === pkg.ecosystem)));
    } catch (err) {
      setPkgError(String(err).replace(/^Error:\s*/, ''));
    }
  }

  async function handleSend(text) {
    const q = (text ?? input).trim();
    if (!q || loading) return;
    setInput('');
    setChatError(null);
    setMessages((prev) => [...prev, { role: 'user', content: q }]);
    setLoading(true);
    try {
      const res = await queryAdvisories(q, { searchMode });
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: res.answer ?? '',
        chunks: res.chunks ?? [],
      }]);
    } catch (err) {
      setChatError(String(err).replace(/^Error:\s*/, ''));
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  }

  return (
    <div className="app-layout">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="kb-section">
          <p className="kb-label">Scan Package</p>
          <form onSubmit={handleIngest} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <input
              className="chat-input"
              type="text"
              placeholder="e.g. pillow, requests"
              value={pkgName}
              onChange={(e) => setPkgName(e.target.value)}
              aria-label="Package name"
            />
            <select
              value={ecosystem}
              onChange={(e) => setEcosystem(e.target.value)}
              aria-label="Ecosystem"
              style={{ padding: '6px 8px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', fontSize: '13px' }}
            >
              {ECOSYSTEMS.map((e) => <option key={e} value={e}>{e}</option>)}
            </select>
            <button
              className="send-btn"
              type="submit"
              disabled={!pkgName.trim() || ingesting}
              style={{ alignSelf: 'flex-end', padding: '6px 14px', fontSize: '13px' }}
            >
              {ingesting ? 'Scanning…' : 'Scan'}
            </button>
          </form>
          {pkgError && <p className="upload-err" role="alert">{pkgError}</p>}
        </div>

        <div className="kb-section">
          <p className="kb-label">Indexed Packages</p>
          {packages.length === 0 && <p className="kb-empty">No packages yet.</p>}
          <ul className="kb-list" aria-label="Indexed packages">
            {packages.map((pkg) => (
              <li key={`${pkg.name}::${pkg.ecosystem}`} className="kb-item">
                <span className="kb-name" title={`${pkg.name} (${pkg.ecosystem})`}>
                  {pkg.name}
                  <span style={{ opacity: 0.5, fontSize: '11px', marginLeft: '4px' }}>
                    {pkg.ecosystem}
                  </span>
                </span>
                <span className="kb-meta">
                  <PackageStatus status={pkg.status} />
                  {pkg.status === 'indexed' && (
                    <span style={{ fontSize: '11px', opacity: 0.55 }}>
                      {pkg.advisory_count} {pkg.advisory_count === 1 ? 'advisory' : 'advisories'}
                    </span>
                  )}
                  <button
                    className="kb-delete"
                    onClick={() => handleDelete(pkg)}
                    aria-label={`Remove ${pkg.name}`}
                  >
                    <TrashIcon />
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* ── Chat panel ── */}
      <main className="chat-panel">
        <div className="chat-container">
          <div ref={threadRef} className="chat-thread" aria-live="polite" aria-label="Security conversation">
            {messages.length === 0 && !loading && (
              <div className="chat-empty">
                <p>Scan a package, then ask about its vulnerabilities.</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '12px', justifyContent: 'center' }}>
                  {STARTER_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      className="source-chip"
                      style={{ cursor: 'pointer', background: 'var(--bg-raised)' }}
                      onClick={() => handleSend(q)}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`msg msg-${msg.role}`}>
                <div className="msg-bubble">{msg.content}</div>
                {msg.role === 'assistant' && msg.chunks?.length > 0 && (
                  <div className="msg-sources" aria-label="Sources">
                    {msg.chunks.map((c, j) => (
                      <span key={j} className="source-chip">
                        {c.advisory_id || c.filename} <ArrowIcon />
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="msg msg-assistant" aria-label="Assistant is responding">
                <div className="msg-bubble typing-indicator"><span /><span /><span /></div>
              </div>
            )}
          </div>

          {chatError && <p className="chat-error" role="alert">{chatError}</p>}

          <div className="chat-input-bar">
            <div className="mode-toggle" role="group" aria-label="Search mode">
              {MODES.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  className={searchMode === m.value ? 'active' : ''}
                  onClick={() => setSearchMode(m.value)}
                  aria-pressed={searchMode === m.value}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <form className="chat-input-row" onSubmit={(e) => { e.preventDefault(); handleSend(); }}>
              <input
                className="chat-input"
                type="text"
                placeholder="Ask about vulnerabilities…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                aria-label="Security question"
              />
              <button
                className="send-btn"
                type="submit"
                disabled={!input.trim() || loading}
                aria-label="Send"
              >
                <SendIcon />
              </button>
            </form>
            <p className="chat-disclaimer">AI-generated content may be inaccurate. Verify advisories at nvd.nist.gov.</p>
          </div>
        </div>
      </main>
    </div>
  );
}

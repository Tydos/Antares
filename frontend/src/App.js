import UploadSection from './components/UploadSection';
import DocumentsSection from './components/DocumentsSection';

export default function App() {
  return (
    <div className="layout">
      <header className="site-header">
        <div className="header-inner">
          <div>
            <h1>RAG PDF</h1>
            <p className="tagline">Upload PDFs to Vercel Blob</p>
          </div>
        </div>
      </header>

      <main className="site-main">
        <UploadSection />
        <DocumentsSection />
      </main>

      <footer className="site-footer">
        <p>PDF uploads &mdash; Vercel Blob + PostgreSQL</p>
      </footer>
    </div>
  );
}

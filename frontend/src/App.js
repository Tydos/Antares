import UploadSection from './components/UploadSection';
import SearchSection from './components/SearchSection';
import DocumentsSection from './components/DocumentsSection';

export default function App() {
  return (
    <div className="layout">
      <header className="site-header">
        <div className="header-inner">
          <div>
            <h1>RAG PDF Search</h1>
            <p className="tagline">Upload, index and search your PDFs</p>
          </div>
        </div>
      </header>

      <main className="site-main">
        <UploadSection />
        <SearchSection />
        <DocumentsSection />
      </main>

      <footer className="site-footer">
        <p>RAG PDF Hybrid Search &mdash; Elasticsearch + MinIO</p>
      </footer>
    </div>
  );
}

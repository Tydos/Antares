import UploadSection from './components/UploadSection';
import SearchSection from './components/SearchSection';
import DocumentsSection from './components/DocumentsSection';

export default function App() {
  return (
    <>
      <h1>RAG PDF Search</h1>
      <UploadSection />
      <SearchSection />
      <DocumentsSection />
    </>
  );
}

import UploadSection from './components/UploadSection';
import DocumentsSection from './components/DocumentsSection';
import ChatSection from './components/ChatSection';

export default function App() {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Not ChatGPT</h1>
        </div>
        <UploadSection />
        <DocumentsSection />
      </aside>
      <main className="chat-panel">
        <ChatSection />
      </main>
    </div>
  );
}

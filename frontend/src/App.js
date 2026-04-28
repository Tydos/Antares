import { useState } from 'react';
import UploadSection from './components/UploadSection';
import DocumentsSection from './components/DocumentsSection';
import ChatSection from './components/ChatSection';

export default function App() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>Not ChatGPT</h1>
        </div>
        <UploadSection onSuccess={() => setRefreshKey((k) => k + 1)} />
        <DocumentsSection refreshKey={refreshKey} />
      </aside>
      <main className="chat-panel">
        <ChatSection />
      </main>
    </div>
  );
}

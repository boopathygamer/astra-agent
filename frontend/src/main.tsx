import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import App from './App.tsx';
import Chat from './Chat.tsx';
import AgentPage from './AgentPage.tsx';
import TutorPage from './TutorPage.tsx';
import AppDevPage from './AppDevPage.tsx';
import WebDevPage from './WebDevPage.tsx';
import GameDevPage from './GameDevPage.tsx';
import { WebLLMProvider } from './contexts/WebLLMContext';
import { GlobalWebLLMWidget } from './components/GlobalWebLLMWidget';
import './index.css';
import { registerSW } from 'virtual:pwa-register';

// Initialize Service Worker for PWA (Offline Mode)
if ('serviceWorker' in navigator) {
  registerSW({ immediate: true });
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WebLLMProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<App />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/agent" element={<AgentPage />} />
          <Route path="/tutor" element={<TutorPage />} />
          <Route path="/app-dev" element={<AppDevPage />} />
          <Route path="/web-dev" element={<WebDevPage />} />
          <Route path="/game-dev" element={<GameDevPage />} />
        </Routes>
        <GlobalWebLLMWidget />
      </BrowserRouter>
    </WebLLMProvider>
  </StrictMode>,
);

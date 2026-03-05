import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  SquarePen,
  Search,
  GraduationCap,
  LayoutGrid,
  Code,
  Folder,
  UserPlus,
  RefreshCcw,
  Plus,
  Mic,
  AudioLines,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  FileText,
  BrainCircuit,
  Image as ImageIcon,
  Bot,
  Smartphone,
  Cpu,
  Settings,
  X,
  User,
  Key,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Shield,
  ShieldAlert,
  ShieldCheck,
  FolderSearch,
  Globe,
  Trash2,
  Archive,
  Activity,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  sendChat, configureProviders, checkHealth, type ProviderKeys,
  scanFile, scanDirectory, scanUrl, getScanStats, getScanHistory,
  quarantineFile, destroyThreat
} from './api';

const CustomLogo = ({ className = "w-6 h-6" }: { className?: string }) => {
  const grid = [
    ".....1111.......",
    "....111111......",
    "....111111......",
    "....1111111.....",
    "....111111......",
    "....1...11......",
    "....11..11......",
    "....111111......",
    "....111111.11...",
    "....1111...11...",
    "....11111..1....",
    ".....111........",
    "......111.......",
    ".......111......",
    ".......11.......",
  ];

  return (
    <svg viewBox="0 0 16 15" className={className} fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      {grid.map((row, y) =>
        row.split('').map((cell, x) =>
          cell === '1' ? <rect key={`${x}-${y}`} x={x} y={y} width="1.05" height="1.05" /> : null
        )
      )}
    </svg>
  );
};

export default function Chat() {
  const [isSidebarOpen, setSidebarOpen] = useState(window.innerWidth >= 768);
  const [isPlusMenuOpen, setPlusMenuOpen] = useState(false);
  const [isSettingsOpen, setSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<'account' | 'api'>('account');
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<{ text: string, isUser: boolean }[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [apiKeys, setApiKeys] = useState<ProviderKeys>({});
  const [configStatus, setConfigStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [configMessage, setConfigMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const plusMenuRef = useRef<HTMLDivElement>(null);

  // ── Core Agent Scanner State ──
  const [isScannerOpen, setScannerOpen] = useState(false);
  const [scanMode, setScanMode] = useState<'file' | 'directory' | 'url'>('directory');
  const [scanInput, setScanInput] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [scanResults, setScanResults] = useState<any>(null);
  const [scanStats, setScanStats] = useState<any>(null);
  const [scanError, setScanError] = useState('');
  const [actionStatus, setActionStatus] = useState<Record<string, string>>({});
  const [expandedResult, setExpandedResult] = useState<number | null>(null);

  // ── Health Check ──
  useEffect(() => {
    const checkBackend = async () => {
      try {
        await checkHealth();
        setBackendStatus('connected');
      } catch {
        setBackendStatus('disconnected');
      }
    };
    checkBackend();
    const interval = setInterval(checkBackend, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (plusMenuRef.current && !plusMenuRef.current.contains(event.target as Node)) {
        setPlusMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setMessages(prev => [...prev, { text: userMessage, isUser: true }]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await sendChat(userMessage);
      setMessages(prev => [...prev, { text: res.answer, isUser: false }]);
      setBackendStatus('connected');
    } catch (err: any) {
      const errorMsg = err?.message || 'Failed to reach the backend. Make sure the server is running.';
      setMessages(prev => [...prev, { text: `⚠️ ${errorMsg}`, isUser: false }]);
      if (errorMsg.includes('fetch') || errorMsg.includes('network') || errorMsg.includes('Failed')) {
        setBackendStatus('disconnected');
      }
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading]);

  const handleConnectAPIs = useCallback(async () => {
    const hasAnyKey = Object.values(apiKeys).some(v => typeof v === 'string' && v.trim());
    if (!hasAnyKey) {
      setConfigStatus('error');
      setConfigMessage('Please enter at least one API key.');
      return;
    }

    setConfigStatus('saving');
    try {
      const result = await configureProviders(apiKeys);
      setConfigStatus('success');
      setConfigMessage(`Connected ${result.providers_updated.length} provider(s): ${result.providers_updated.join(', ')}`);
      setBackendStatus('connected');
    } catch (err: any) {
      setConfigStatus('error');
      setConfigMessage(err?.message || 'Failed to configure providers.');
    }
  }, [apiKeys]);

  // ── Core Agent Scanner Handlers ──
  const handleScan = useCallback(async () => {
    if (!scanInput.trim() || isScanning) return;
    setIsScanning(true);
    setScanResults(null);
    setScanError('');
    setExpandedResult(null);

    try {
      let result;
      if (scanMode === 'directory') {
        result = await scanDirectory(scanInput.trim());
      } else if (scanMode === 'file') {
        result = await scanFile(scanInput.trim());
      } else {
        result = await scanUrl(scanInput.trim());
      }
      setScanResults(result);
      // Refresh stats
      getScanStats().then(setScanStats).catch(() => { });
    } catch (err: any) {
      setScanError(err?.message || 'Scan failed. Make sure the backend is running.');
    } finally {
      setIsScanning(false);
    }
  }, [scanInput, scanMode, isScanning]);

  const handleAction = useCallback(async (action: 'quarantine' | 'destroy', filePath: string) => {
    setActionStatus(prev => ({ ...prev, [filePath]: 'loading' }));
    try {
      if (action === 'quarantine') {
        await quarantineFile(filePath);
        setActionStatus(prev => ({ ...prev, [filePath]: 'quarantined' }));
      } else {
        await destroyThreat(filePath);
        setActionStatus(prev => ({ ...prev, [filePath]: 'destroyed' }));
      }
      getScanStats().then(setScanStats).catch(() => { });
    } catch (err: any) {
      setScanError(err?.message || `Failed to ${action} file.`);
      setActionStatus(prev => ({ ...prev, [filePath]: 'error' }));
    }
  }, []);

  return (
    <div className="flex h-screen bg-[#0a0a0a] text-white font-sans overflow-hidden selection:bg-emerald-500/30">
      {/* Mobile Sidebar Backdrop */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <AnimatePresence mode="wait">
        {isSidebarOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 260, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="fixed md:relative h-full z-30 bg-black border-r border-white/10 flex flex-col overflow-hidden shadow-2xl md:shadow-none"
          >
            <div className="p-3 flex items-center justify-between">
              <Link to="/" className="flex items-center gap-2 hover:bg-white/5 p-2 rounded-lg transition-colors text-white/90 hover:text-white">
                <CustomLogo className="w-5 h-5 text-white" />
              </Link>
              <button onClick={() => setSidebarOpen(false)} className="p-2 text-white/50 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
                <PanelLeftClose className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar px-3 pb-3">
              <div className="space-y-0.5 mb-6">
                <button className="w-full flex items-center gap-3 px-2 py-2 text-sm text-white/80 hover:bg-white/5 hover:text-white rounded-lg transition-colors">
                  <SquarePen className="w-4 h-4" />
                  New chat
                </button>
                <Link to="/tutor" className="w-full flex items-center gap-3 px-2 py-2 text-sm text-white/80 hover:bg-white/5 hover:text-white rounded-lg transition-colors">
                  <GraduationCap className="w-4 h-4" />
                  Tutor
                </Link>
                <Link to="/app-dev" className="w-full flex items-center gap-3 px-2 py-2 text-sm text-white/80 hover:bg-white/5 hover:text-white rounded-lg transition-colors">
                  <Smartphone className="w-4 h-4" />
                  App Dev
                </Link>
                <Link to="/web-dev" className="w-full flex items-center gap-3 px-2 py-2 text-sm text-white/80 hover:bg-white/5 hover:text-white rounded-lg transition-colors">
                  <Code className="w-4 h-4" />
                  Web Dev
                </Link>
              </div>
            </div>

            <div className="p-3 border-t border-white/10">
              <button
                onClick={() => setSettingsOpen(true)}
                className="w-full flex items-center gap-3 px-2 py-2 text-sm text-white/80 hover:bg-white/5 hover:text-white rounded-lg transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-white/80">
                  <Settings className="w-4 h-4" />
                </div>
                <div className="flex flex-col items-start">
                  <span className="font-medium">Settings</span>
                  <span className="text-xs text-white/40">Manage account & APIs</span>
                </div>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Area */}
      <div className="flex-1 flex flex-col relative min-w-0">
        {/* Header */}
        <header className="h-14 flex items-center justify-between px-4 sticky top-0 bg-[#0a0a0a]/80 backdrop-blur-md z-10 border-b border-white/5">
          <div className="flex items-center gap-2">
            {!isSidebarOpen && (
              <button onClick={() => setSidebarOpen(true)} className="p-2 text-white/50 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
                <PanelLeftOpen className="w-5 h-5" />
              </button>
            )}
            <div className="flex items-center gap-2 text-lg font-medium text-white/90 px-3 py-1.5">
              Autonomous Agent
              <div className={`w-2 h-2 rounded-full transition-colors ${backendStatus === 'connected' ? 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)]' :
                backendStatus === 'disconnected' ? 'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]' :
                  'bg-yellow-500 animate-pulse'
                }`} title={backendStatus === 'connected' ? 'Backend connected' : backendStatus === 'disconnected' ? 'Backend offline' : 'Checking...'} />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/agent" className="p-2 text-white/50 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
              <Bot className="w-5 h-5" />
            </Link>
            <button className="p-2 text-white/50 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
              <UserPlus className="w-5 h-5" />
            </button>
            <button className="p-2 text-white/50 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
              <RefreshCcw className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col">
          {messages.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center px-6">
              <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-6 border border-white/10 shadow-[0_0_30px_rgba(255,255,255,0.1)]">
                <CustomLogo className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-3xl font-medium mb-8 text-white tracking-tight">What are you working on?</h1>
            </div>
          ) : (
            <div className="flex-1 w-full max-w-3xl mx-auto px-4 py-8 space-y-8">
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.isUser ? 'justify-end' : 'justify-start'}`}>
                  {msg.isUser ? (
                    <div className="max-w-[80%] rounded-2xl px-4 py-2.5 bg-[#2f2f2f] text-white/90 border border-white/5 shadow-sm">
                      <div className="whitespace-pre-wrap leading-relaxed text-sm" id={`msg-user-${idx}`}>
                        {msg.text}
                      </div>
                    </div>
                  ) : (
                    <div className="max-w-[85%] flex gap-4">
                      <div className="w-8 h-8 rounded-full bg-white/10 border border-white/20 flex items-center justify-center flex-shrink-0 mt-1">
                        <CustomLogo className="w-5 h-5 text-white" />
                      </div>
                      <div className="pt-1.5 text-white/90">
                        <div className="whitespace-pre-wrap leading-relaxed">
                          {msg.text}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] flex gap-4">
                    <div className="w-8 h-8 rounded-full bg-white/10 border border-white/20 flex items-center justify-center flex-shrink-0 mt-1">
                      <CustomLogo className="w-5 h-5 text-white" />
                    </div>
                    <div className="pt-2 flex items-center gap-2 text-white/50">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span className="text-sm">Thinking...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-4 w-full max-w-3xl mx-auto relative">
          <AnimatePresence>
            {isPlusMenuOpen && (
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="absolute bottom-[calc(100%-1rem)] left-4 bg-[#2f2f2f] border border-white/10 rounded-lg p-1 shadow-2xl z-50 w-40"
                ref={plusMenuRef}
              >
                <div className="flex flex-col gap-0.5">
                  <button
                    className="flex items-center gap-2.5 px-2.5 py-1.5 text-[13px] font-medium text-white/90 hover:bg-white/10 rounded-md transition-colors w-full text-left"
                    onClick={() => { setPlusMenuOpen(false); setScannerOpen(true); getScanStats().then(setScanStats).catch(() => { }); }}
                  >
                    <Cpu className="w-3.5 h-3.5 text-emerald-400" />
                    Core Agent
                  </button>
                  <button
                    className="flex items-center gap-2.5 px-2.5 py-1.5 text-[13px] font-medium text-white/90 hover:bg-white/10 rounded-md transition-colors w-full text-left"
                    onClick={() => setPlusMenuOpen(false)}
                  >
                    <ImageIcon className="w-3.5 h-3.5 text-emerald-400" />
                    Images
                  </button>
                  <button
                    className="flex items-center gap-2.5 px-2.5 py-1.5 text-[13px] font-medium text-white/90 hover:bg-white/10 rounded-md transition-colors w-full text-left"
                    onClick={() => setPlusMenuOpen(false)}
                  >
                    <FileText className="w-3.5 h-3.5 text-emerald-400" />
                    Files
                  </button>
                  <button
                    className="flex items-center gap-2.5 px-2.5 py-1.5 text-[13px] font-medium text-white/90 hover:bg-white/10 rounded-md transition-colors w-full text-left"
                    onClick={() => setPlusMenuOpen(false)}
                  >
                    <BrainCircuit className="w-3.5 h-3.5 text-emerald-400" />
                    Deep Researcher
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <form onSubmit={handleSubmit} className="relative flex items-center bg-[#141414] border border-white/10 rounded-full px-4 py-3 focus-within:border-emerald-500/50 focus-within:bg-[#1a1a1a] focus-within:shadow-[0_0_20px_rgba(16,185,129,0.05)] transition-all duration-300">
            <button
              type="button"
              onClick={() => setPlusMenuOpen(!isPlusMenuOpen)}
              className={`p-1 transition-colors rounded-full ${isPlusMenuOpen ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white'}`}
            >
              <Plus className={`w-6 h-6 transition-transform duration-200 ${isPlusMenuOpen ? 'rotate-45' : ''}`} />
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything"
              className="flex-1 bg-transparent border-none outline-none px-3 text-white placeholder-white/30 text-base"
            />
            <div className="flex items-center gap-2">
              {!input.trim() ? (
                <>
                  <button type="button" className="p-2 text-white/40 hover:text-white transition-colors">
                    <Mic className="w-5 h-5" />
                  </button>
                  <button type="button" className="p-2 bg-white text-black rounded-full hover:bg-gray-200 transition-colors">
                    <Send className="w-5 h-5" />
                  </button>
                </>
              ) : (
                <button type="submit" className="p-2 bg-emerald-500 text-black rounded-full hover:bg-emerald-400 transition-colors shadow-[0_0_10px_rgba(16,185,129,0.3)]">
                  <Send className="w-5 h-5" />
                </button>
              )}
            </div>
          </form>
          <div className="text-center mt-3 text-xs text-white/30">
            Astra Agent can make mistakes. Check important info.
          </div>
        </div>
      </div>

      {/* Settings Modal */}
      <AnimatePresence>
        {isSettingsOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSettingsOpen(false)}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl bg-[#141414] border border-white/10 rounded-2xl shadow-2xl z-50 overflow-hidden flex flex-col max-h-[85vh]"
            >
              <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
                <h2 className="text-lg font-semibold text-white">Settings</h2>
                <button
                  onClick={() => setSettingsOpen(false)}
                  className="p-2 text-white/50 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex flex-1 overflow-hidden">
                {/* Sidebar */}
                <div className="w-48 border-r border-white/10 p-4 flex flex-col gap-2">
                  <button
                    onClick={() => setSettingsTab('account')}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${settingsTab === 'account'
                      ? 'bg-white/10 text-white'
                      : 'text-white/60 hover:bg-white/5 hover:text-white'
                      }`}
                  >
                    <User className="w-4 h-4" />
                    Account
                  </button>
                  <button
                    onClick={() => setSettingsTab('api')}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${settingsTab === 'api'
                      ? 'bg-white/10 text-white'
                      : 'text-white/60 hover:bg-white/5 hover:text-white'
                      }`}
                  >
                    <Key className="w-4 h-4" />
                    API Keys
                  </button>
                </div>

                {/* Content */}
                <div className="flex-1 p-6 overflow-y-auto custom-scrollbar">
                  {settingsTab === 'account' ? (
                    <div className="space-y-6">
                      <div className="flex items-center gap-4">
                        <div className="w-16 h-16 rounded-full bg-emerald-500 flex items-center justify-center text-2xl font-bold text-black">
                          BG
                        </div>
                        <div>
                          <h3 className="text-lg font-medium text-white">Boopathy Gamer</h3>
                          <p className="text-sm text-emerald-400">Pro Plan</p>
                        </div>
                      </div>
                      <div className="space-y-4">
                        <div className="space-y-2">
                          <label className="text-sm font-medium text-white/60">Email Address</label>
                          <input
                            type="email"
                            disabled
                            value="boopathygamer420@gmail.com"
                            className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white/50 cursor-not-allowed"
                          />
                        </div>
                        <button className="px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-sm font-medium text-white transition-colors">
                          Manage Subscription
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      <div>
                        <h3 className="text-lg font-medium text-white mb-1">API Configuration</h3>
                        <p className="text-sm text-white/50 mb-6">Connect your external services to power the autonomous agent.</p>
                      </div>

                      <div className="space-y-4">
                        {[
                          { name: 'OpenAI API Key', placeholder: 'sk-proj-...', key: 'openai_api_key' as const },
                          { name: 'Anthropic API Key', placeholder: 'sk-ant-...', key: 'claude_api_key' as const },
                          { name: 'Google Gemini API Key', placeholder: 'AIzaSy...', key: 'gemini_api_key' as const },
                          { name: 'Grok API Key', placeholder: 'xai-...', key: 'grok_api_key' as const },
                          { name: 'OpenRouter API Key', placeholder: 'sk-or-...', key: 'openrouter_api_key' as const }
                        ].map((api, idx) => (
                          <div key={idx} className="space-y-1.5">
                            <label className="text-sm font-medium text-white/80">{api.name}</label>
                            <input
                              type="password"
                              placeholder={api.placeholder}
                              value={(apiKeys as any)[api.key] || ''}
                              onChange={(e) => setApiKeys(prev => ({ ...prev, [api.key]: e.target.value }))}
                              className="w-full bg-[#0a0a0a] border border-white/10 focus:border-emerald-500/50 rounded-lg px-4 py-2.5 text-white placeholder-white/20 outline-none transition-colors"
                            />
                          </div>
                        ))}
                      </div>

                      {configMessage && (
                        <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${configStatus === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                          configStatus === 'error' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                            'bg-white/5 text-white/60'
                          }`}>
                          {configStatus === 'success' ? <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> :
                            configStatus === 'error' ? <AlertTriangle className="w-4 h-4 flex-shrink-0" /> : null}
                          {configMessage}
                        </div>
                      )}

                      <div className="pt-4 mt-6 border-t border-white/10 flex justify-end">
                        <button
                          onClick={handleConnectAPIs}
                          disabled={configStatus === 'saving'}
                          className="px-6 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-black font-medium rounded-lg transition-colors shadow-[0_0_15px_rgba(16,185,129,0.2)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                          {configStatus === 'saving' && <Loader2 className="w-4 h-4 animate-spin" />}
                          {configStatus === 'saving' ? 'Connecting...' : 'Connect APIs'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Core Agent Scanner Modal */}
      <AnimatePresence>
        {isScannerOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setScannerOpen(false)}
              className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-3xl bg-[#0c0c0c] border border-red-500/20 rounded-2xl shadow-[0_0_60px_rgba(239,68,68,0.08)] z-50 overflow-hidden flex flex-col max-h-[90vh]"
            >
              {/* Scanner Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-red-500/10 bg-gradient-to-r from-red-500/5 to-transparent">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-red-500/10 rounded-lg border border-red-500/20">
                    <ShieldAlert className="w-5 h-5 text-red-400" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                      Core Agent <span className="text-[10px] font-mono bg-red-500/20 text-red-400 px-2 py-0.5 rounded border border-red-500/20">SECURITY</span>
                    </h2>
                    <p className="text-[11px] text-white/30 font-mono">3-STAGE CASCADE DEEP-SCAN ENGINE</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {scanStats && (
                    <div className="flex items-center gap-3 text-[10px] font-mono text-white/25">
                      <span>SCANS: {scanStats.total_scans || 0}</span>
                      <span className="text-red-400">THREATS: {scanStats.threats_detected || 0}</span>
                    </div>
                  )}
                  <button onClick={() => setScannerOpen(false)} className="p-2 text-white/40 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Scan Mode Tabs */}
              <div className="flex gap-1 px-6 pt-4 pb-2">
                {[
                  { mode: 'directory' as const, icon: FolderSearch, label: 'Deep Search' },
                  { mode: 'file' as const, icon: FileText, label: 'Scan File' },
                  { mode: 'url' as const, icon: Globe, label: 'Scan URL' },
                ].map(({ mode, icon: Icon, label }) => (
                  <button
                    key={mode}
                    onClick={() => { setScanMode(mode); setScanResults(null); setScanError(''); }}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${scanMode === mode
                      ? 'bg-red-500/15 text-red-400 border border-red-500/20 shadow-[0_0_10px_rgba(239,68,68,0.1)]'
                      : 'text-white/30 hover:text-white/60 hover:bg-white/5'
                      }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {label}
                  </button>
                ))}
              </div>

              {/* Scan Input */}
              <div className="px-6 py-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={scanInput}
                    onChange={(e) => setScanInput(e.target.value)}
                    placeholder={
                      scanMode === 'directory' ? 'C:\\Users\\user\\Downloads' :
                        scanMode === 'file' ? 'C:\\path\\to\\file.exe' :
                          'https://suspicious-site.com'
                    }
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && scanInput.trim() && !isScanning) {
                        e.preventDefault();
                        handleScan();
                      }
                    }}
                    className="flex-1 bg-[#141414] border border-white/10 focus:border-red-500/40 rounded-lg px-4 py-3 text-sm text-white placeholder-white/20 outline-none transition-colors font-mono"
                  />
                  <button
                    onClick={handleScan}
                    disabled={!scanInput.trim() || isScanning}
                    className="px-6 py-3 bg-red-500/80 hover:bg-red-500 text-white font-bold rounded-lg transition-all disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-2 shadow-[0_0_15px_rgba(239,68,68,0.2)]"
                  >
                    {isScanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
                    {isScanning ? 'Scanning...' : 'Scan'}
                  </button>
                </div>
                {scanMode === 'directory' && (
                  <p className="text-[10px] text-white/20 mt-1.5 font-mono">Deep recursive scan — inspects every file for virus, malware, trojan, ransomware, spyware, rootkit</p>
                )}
              </div>

              {/* Error */}
              {scanError && (
                <div className="mx-6 mb-3 flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-400">
                  <XCircle className="w-4 h-4 flex-shrink-0" /> {scanError}
                </div>
              )}

              {/* Results */}
              <div className="flex-1 overflow-y-auto custom-scrollbar px-6 pb-6">
                {scanResults && (
                  <div className="space-y-2">
                    {/* Directory header */}
                    {scanResults.files_scanned !== undefined && (
                      <div className="flex items-center justify-between py-3 border-b border-white/5 mb-3">
                        <div className="flex items-center gap-3">
                          <span className="text-sm text-white/60">Scanned <span className="text-white font-bold">{scanResults.files_scanned}</span> files</span>
                          {scanResults.threats_found > 0 ? (
                            <span className="flex items-center gap-1 text-xs font-bold text-red-400 bg-red-500/10 px-2 py-1 rounded border border-red-500/20">
                              <ShieldAlert className="w-3 h-3" /> {scanResults.threats_found} THREAT{scanResults.threats_found > 1 ? 'S' : ''}
                            </span>
                          ) : (
                            <span className="flex items-center gap-1 text-xs font-bold text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded border border-emerald-500/20">
                              <ShieldCheck className="w-3 h-3" /> ALL CLEAR
                            </span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Single file/URL result */}
                    {scanResults.scan_id && (
                      <div className={`p-4 rounded-xl border ${scanResults.is_threat
                        ? 'bg-red-500/5 border-red-500/20'
                        : 'bg-emerald-500/5 border-emerald-500/20'
                        }`}>
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            {scanResults.is_threat ? <ShieldAlert className="w-5 h-5 text-red-400" /> : <ShieldCheck className="w-5 h-5 text-emerald-400" />}
                            <span className={`text-sm font-bold ${scanResults.is_threat ? 'text-red-400' : 'text-emerald-400'}`}>
                              {scanResults.is_threat ? 'THREAT DETECTED' : 'CLEAN'}
                            </span>
                          </div>
                          <span className="text-[10px] font-mono text-white/20">{scanResults.scan_id}</span>
                        </div>
                        {scanResults.threat_type && (
                          <div className="flex flex-wrap gap-2 mb-3">
                            <span className="text-[10px] font-bold uppercase bg-red-500/15 text-red-400 px-2 py-0.5 rounded border border-red-500/20">{scanResults.threat_type}</span>
                            {scanResults.severity && <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${scanResults.severity === 'critical' ? 'bg-red-600/15 text-red-500 border-red-600/20' :
                              scanResults.severity === 'high' ? 'bg-orange-500/15 text-orange-400 border-orange-500/20' :
                                scanResults.severity === 'medium' ? 'bg-amber-500/15 text-amber-400 border-amber-500/20' :
                                  'bg-yellow-500/15 text-yellow-400 border-yellow-500/20'
                              }`}>{scanResults.severity}</span>}
                            <span className="text-[10px] font-mono text-white/30">Confidence: {(scanResults.confidence * 100).toFixed(0)}%</span>
                          </div>
                        )}
                        {scanResults.recommended_action && scanResults.recommended_action !== 'allow' && (
                          <div className="flex gap-2 mt-3">
                            <button
                              onClick={() => handleAction('quarantine', scanResults.target || scanInput)}
                              disabled={actionStatus[scanResults.target || scanInput] === 'loading'}
                              className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-500/15 hover:bg-amber-500/25 text-amber-400 text-xs font-bold rounded-lg border border-amber-500/20 transition-colors"
                            >
                              <Archive className="w-3 h-3" /> Quarantine
                            </button>
                            <button
                              onClick={() => handleAction('destroy', scanResults.target || scanInput)}
                              disabled={actionStatus[scanResults.target || scanInput] === 'loading'}
                              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/15 hover:bg-red-500/25 text-red-400 text-xs font-bold rounded-lg border border-red-500/20 transition-colors"
                            >
                              <Trash2 className="w-3 h-3" /> Destroy
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Directory results list */}
                    {scanResults.results && scanResults.results.map((r: any, i: number) => (
                      <div
                        key={i}
                        className={`rounded-xl border transition-all cursor-pointer ${r.is_threat
                          ? 'bg-red-500/5 border-red-500/15 hover:border-red-500/30'
                          : 'bg-white/[0.02] border-white/5 hover:border-white/10'
                          }`}
                        onClick={() => setExpandedResult(expandedResult === i ? null : i)}
                      >
                        <div className="flex items-center gap-3 px-4 py-3">
                          {r.is_threat ? <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0" /> : <ShieldCheck className="w-4 h-4 text-emerald-500/40 flex-shrink-0" />}
                          <span className="text-[11px] font-mono text-white/50 truncate flex-1">{r.file}</span>
                          {r.is_threat && (
                            <span className="text-[9px] font-bold uppercase bg-red-500/15 text-red-400 px-1.5 py-0.5 rounded border border-red-500/20">{r.threat_type}</span>
                          )}
                          {r.severity && (
                            <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded border ${r.severity === 'critical' ? 'bg-red-600/15 text-red-500 border-red-600/20' :
                              r.severity === 'high' ? 'bg-orange-500/15 text-orange-400 border-orange-500/20' :
                                r.severity === 'medium' ? 'bg-amber-500/15 text-amber-400 border-amber-500/20' :
                                  'bg-emerald-500/10 text-emerald-400/60 border-emerald-500/10'
                              }`}>{r.severity || 'clean'}</span>
                          )}
                          {expandedResult === i ? <ChevronUp className="w-3 h-3 text-white/20" /> : <ChevronDown className="w-3 h-3 text-white/20" />}
                        </div>

                        <AnimatePresence>
                          {expandedResult === i && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden"
                            >
                              <div className="px-4 pb-3 border-t border-white/5 pt-3">
                                <p className="text-[11px] text-white/30 mb-2">{r.summary}</p>
                                {r.confidence !== undefined && <p className="text-[10px] font-mono text-white/20">Confidence: {(r.confidence * 100).toFixed(0)}% | Action: {r.recommended_action}</p>}
                                {r.is_threat && (
                                  <div className="flex gap-2 mt-2">
                                    <button
                                      onClick={(e) => { e.stopPropagation(); handleAction('quarantine', r.file); }}
                                      disabled={actionStatus[r.file] === 'loading'}
                                      className="flex items-center gap-1 px-2 py-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 text-[10px] font-bold rounded border border-amber-500/20 transition-colors"
                                    >
                                      {actionStatus[r.file] === 'quarantined' ? <><CheckCircle2 className="w-2.5 h-2.5" /> Done</> : <><Archive className="w-2.5 h-2.5" /> Quarantine</>}
                                    </button>
                                    <button
                                      onClick={(e) => { e.stopPropagation(); handleAction('destroy', r.file); }}
                                      disabled={actionStatus[r.file] === 'loading'}
                                      className="flex items-center gap-1 px-2 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-400 text-[10px] font-bold rounded border border-red-500/20 transition-colors"
                                    >
                                      {actionStatus[r.file] === 'destroyed' ? <><CheckCircle2 className="w-2.5 h-2.5" /> Destroyed</> : <><Trash2 className="w-2.5 h-2.5" /> Destroy</>}
                                    </button>
                                  </div>
                                )}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    ))}
                  </div>
                )}

                {/* Empty state */}
                {!scanResults && !isScanning && !scanError && (
                  <div className="flex flex-col items-center justify-center py-16 text-white/15">
                    <Shield className="w-12 h-12 mb-4" />
                    <span className="text-sm font-medium">Enter a path or URL to scan</span>
                    <span className="text-xs mt-1">Deep search for virus, malware, trojan, ransomware, spyware, rootkit, backdoor</span>
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="h-8 border-t border-red-500/10 bg-[#0a0a0a] flex items-center px-6 text-[9px] font-mono text-white/15">
                <span>POWERED BY ASTRA THREAT SCANNER — 3-STAGE CASCADE · SIGNATURE · HEURISTIC · BEHAVIORAL · DEEP SEMANTIC</span>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

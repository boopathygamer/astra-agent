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
  ChevronUp,
  Link2,
  Copy,
  Terminal,
  Wrench,
  Gamepad2,
  Flame,
  BarChart3,
  Zap
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  sendChat, configureProviders, checkHealth, getProviderStatus, type ProviderKeys,
  scanFile, scanDirectory, scanUrl, getScanStats, getScanHistory,
  quarantineFile, destroyThreat, getMcpConfig, getMcpStatus, type McpStatus
} from './api';
import MarkdownRenderer from './MarkdownRenderer';

// ── Slash Command Tools ────────────────────────────
interface SlashTool {
  id: string;
  name: string;
  description: string;
  category: 'tool' | 'agent';
  emoji: string;
}

const SLASH_TOOLS: SlashTool[] = [
  // ── System Tools ──
  { id: 'calculator', name: 'Calculator', description: 'Advanced math and calculations', category: 'tool', emoji: '🧮' },
  { id: 'code_executor', name: 'Code Runner', description: 'Execute Python/JS code', category: 'tool', emoji: '▶️' },
  { id: 'web_search', name: 'Web Search', description: 'Search the internet', category: 'tool', emoji: '🔍' },
  { id: 'writer', name: 'Writer', description: 'Generate documents and content', category: 'tool', emoji: '✍️' },
  { id: 'data_analyzer', name: 'Data Analyzer', description: 'Analyze and visualize data', category: 'tool', emoji: '📊' },
  { id: 'file_ops', name: 'File Operations', description: 'Read, write, and manage files', category: 'tool', emoji: '📁' },
  { id: 'doc_reader', name: 'Doc Reader', description: 'Read and parse documents', category: 'tool', emoji: '📄' },
  { id: 'image_analyzer', name: 'Image Analyzer', description: 'Analyze and describe images', category: 'tool', emoji: '🖼️' },
  { id: 'knowledge', name: 'Knowledge Base', description: 'Query stored knowledge', category: 'tool', emoji: '🧠' },
  { id: 'task_planner', name: 'Task Planner', description: 'Plan and organize tasks', category: 'tool', emoji: '📋' },
  { id: 'threat_guard', name: 'Threat Guard', description: 'Security scanning and threat detection', category: 'tool', emoji: '🛡️' },
  { id: 'device_ops', name: 'Device Ops', description: 'Device management operations', category: 'tool', emoji: '📱' },
  { id: 'folder_to_ppt', name: 'Folder to PPT', description: 'Convert folder contents to presentation', category: 'tool', emoji: '📽️' },
  { id: 'game_dev_tools', name: 'Game Dev Tools', description: 'Game development utilities', category: 'tool', emoji: '🎮' },
  { id: 'graph_research', name: 'Graph Research', description: 'Graph-based research and math', category: 'tool', emoji: '📈' },
  { id: 'platform_support', name: 'Platform Support', description: 'Cross-platform development support', category: 'tool', emoji: '🖥️' },
  { id: 'tool_forge', name: 'Tool Forge', description: 'Create and manage custom tools', category: 'tool', emoji: '🔨' },
  { id: 'web_tester', name: 'Web Tester', description: 'Test websites and APIs', category: 'tool', emoji: '🧪' },
  { id: 'policy', name: 'Policy Engine', description: 'Tool access control policies', category: 'tool', emoji: '📜' },
  // ── Agent Profiles ──
  { id: 'deep_researcher', name: 'Deep Researcher', description: 'In-depth research and analysis', category: 'agent', emoji: '🔬' },
  { id: 'devils_advocate', name: "Devil's Advocate", description: 'Challenge assumptions and arguments', category: 'agent', emoji: '😈' },
  { id: 'devops_reviewer', name: 'DevOps Reviewer', description: 'Review infrastructure and CI/CD', category: 'agent', emoji: '⚙️' },
  { id: 'game_developer', name: 'Game Developer', description: 'Game design and development', category: 'agent', emoji: '🕹️' },
  { id: 'gamified_tutor', name: 'Gamified Tutor', description: 'Learn through gamification', category: 'agent', emoji: '🎓' },
  { id: 'contract_hunter', name: 'Contract Hunter', description: 'Find and analyze contracts', category: 'agent', emoji: '📑' },
  { id: 'migration_architect', name: 'Migration Architect', description: 'Plan system migrations', category: 'agent', emoji: '🏗️' },
  { id: 'orchestrator', name: 'Multi-Agent Orchestrator', description: 'Coordinate multiple agents', category: 'agent', emoji: '🎼' },
  { id: 'swarm', name: 'Swarm Intelligence', description: 'Collaborative multi-agent swarm', category: 'agent', emoji: '🐝' },
  { id: 'threat_hunter', name: 'Threat Hunter', description: 'Proactive security threat hunting', category: 'agent', emoji: '🕵️' },
];

// ── Token Tracking ──
interface TokenRecord {
  id: string;
  timestamp: Date;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  provider: string;
  model: string;
  message: string;
}

const estimateTokens = (text: string): number => Math.max(1, Math.ceil(text.length / 4));

const CustomLogo = ({ className = "w-6 h-6" }: { className?: string }) => {
  return (
    <img src="/logo.png" className={`${className} object-contain border-0`} alt="Astra Agent Logo" />
  );
};

export default function Chat() {
  const [isSidebarOpen, setSidebarOpen] = useState(window.innerWidth >= 768);
  const [isPlusMenuOpen, setPlusMenuOpen] = useState(false);
  const [isSettingsOpen, setSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<'account' | 'api' | 'mcp' | 'tokens'>('account');

  // ── Token Tracking State ──
  const [tokenRecords, setTokenRecords] = useState<TokenRecord[]>([]);
  const [tokenBudget, setTokenBudget] = useState<number>(1000000); // 1M tokens default

  // ── MCP State ──
  const [mcpStatus, setMcpStatus] = useState<McpStatus | null>(null);
  const [mcpConfigs, setMcpConfigs] = useState<Record<string, any>>({});
  const [mcpSelectedClient, setMcpSelectedClient] = useState<'claude' | 'cursor' | 'vscode'>('claude');
  const [mcpCopied, setMcpCopied] = useState('');
  const [mcpLoading, setMcpLoading] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<{ text: string, isUser: boolean, routedTo?: string, routingDisplay?: string, routingEmoji?: string }[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [apiKeys, setApiKeys] = useState<ProviderKeys>({});
  const [configStatus, setConfigStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [configMessage, setConfigMessage] = useState('');
  const [activeModelName, setActiveModelName] = useState<string>('');
  const [providerList, setProviderList] = useState<any[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const plusMenuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // ── Slash Command State ──
  const [slashMenuOpen, setSlashMenuOpen] = useState(false);
  const [slashFilter, setSlashFilter] = useState('');
  const [slashSelectedIdx, setSlashSelectedIdx] = useState(0);
  const [selectedTool, setSelectedTool] = useState<SlashTool | null>(null);
  const slashMenuRef = useRef<HTMLDivElement>(null);

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

  // ── Fetch active model name for placeholder ──
  useEffect(() => {
    const fetchModel = async () => {
      try {
        const status = await getProviderStatus();
        if (status?.providers?.length) {
          setProviderList(status.providers);
          const active = status.providers.find((p: any) => p.active);
          if (active?.model) {
            setActiveModelName(active.model);
          }
        }
      } catch { /* backend may be offline */ }
    };
    fetchModel();
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
      if (slashMenuRef.current && !slashMenuRef.current.contains(event.target as Node)) {
        setSlashMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ── Slash Command Helpers ──
  const filteredSlashTools = SLASH_TOOLS.filter(t =>
    !slashFilter || t.name.toLowerCase().includes(slashFilter.toLowerCase()) || t.id.includes(slashFilter.toLowerCase()) || t.description.toLowerCase().includes(slashFilter.toLowerCase())
  );

  const handleSlashSelect = useCallback((tool: SlashTool) => {
    setSelectedTool(tool);
    setInput('');
    setSlashMenuOpen(false);
    setSlashFilter('');
    setSlashSelectedIdx(0);
    inputRef.current?.focus();
  }, []);

  const handleRemoveTool = useCallback(() => {
    setSelectedTool(null);
    inputRef.current?.focus();
  }, []);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setInput(val);

    // Don't reopen slash menu if a tool is already selected
    if (selectedTool) {
      setSlashMenuOpen(false);
      return;
    }

    if (val === '/') {
      setSlashMenuOpen(true);
      setSlashFilter('');
      setSlashSelectedIdx(0);
    } else if (val.startsWith('/') && !val.includes(' ')) {
      setSlashMenuOpen(true);
      setSlashFilter(val.slice(1));
      setSlashSelectedIdx(0);
    } else {
      setSlashMenuOpen(false);
    }
  }, [selectedTool]);

  const handleInputKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!slashMenuOpen) return;
    const tools = filteredSlashTools;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSlashSelectedIdx(prev => Math.min(prev + 1, tools.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSlashSelectedIdx(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && tools.length > 0) {
      e.preventDefault();
      handleSlashSelect(tools[slashSelectedIdx]);
    } else if (e.key === 'Escape') {
      setSlashMenuOpen(false);
    }
  }, [slashMenuOpen, filteredSlashTools, slashSelectedIdx, handleSlashSelect]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const rawInput = input.trim();
    // Prepend tool prefix if a tool is selected
    const userMessage = selectedTool ? `/${selectedTool.id} ${rawInput}` : rawInput;
    setMessages(prev => [...prev, { text: rawInput, isUser: true }]);
    setInput('');
    setSelectedTool(null);
    setIsLoading(true);

    try {
      const res = await sendChat(userMessage);
      const promptTk = estimateTokens(userMessage);
      const completionTk = estimateTokens(res.answer);
      setTokenRecords(prev => [{
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        timestamp: new Date(),
        promptTokens: promptTk,
        completionTokens: completionTk,
        totalTokens: promptTk + completionTk,
        provider: res.routed_to || activeModelName || 'unknown',
        model: activeModelName || 'default',
        message: rawInput.slice(0, 60),
      }, ...prev].slice(0, 500));
      setMessages(prev => [...prev, {
        text: res.answer,
        isUser: false,
        routedTo: res.routed_to || undefined,
        routingDisplay: res.routing_display || undefined,
        routingEmoji: res.routing_emoji || undefined,
      }]);
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
                <Link to="/game-dev" className="w-full flex items-center gap-3 px-2 py-2 text-sm text-white/80 hover:bg-white/5 hover:text-white rounded-lg transition-colors">
                  <Gamepad2 className="w-4 h-4" />
                  Game Dev
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
                        {msg.routedTo && msg.routingDisplay && (
                          <div className="flex items-center gap-1.5 mb-1.5">
                            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border bg-violet-500/10 text-violet-400 border-violet-500/20">
                              {msg.routingEmoji} {msg.routingDisplay}
                            </span>
                          </div>
                        )}
                        <MarkdownRenderer content={msg.text} />
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
          {/* Plus Menu */}
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
                    onClick={() => { setPlusMenuOpen(false); setSlashMenuOpen(true); setSlashFilter(''); setSlashSelectedIdx(0); inputRef.current?.focus(); }}
                  >
                    <Folder className="w-3.5 h-3.5 text-emerald-400" />
                    Tools
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Slash Command Dropdown */}
          <AnimatePresence>
            {slashMenuOpen && filteredSlashTools.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 8, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.97 }}
                transition={{ duration: 0.15 }}
                ref={slashMenuRef}
                className="absolute bottom-[calc(100%-0.5rem)] left-4 right-4 bg-[#1c1c1c] border border-white/10 rounded-xl shadow-[0_16px_48px_rgba(0,0,0,0.6)] z-50 max-h-[340px] overflow-hidden flex flex-col"
              >
                <div className="px-3 py-2 border-b border-white/5 flex items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/30">Tools & Agents</span>
                  <span className="text-[10px] text-white/15">— type to filter</span>
                </div>
                <div className="overflow-y-auto custom-scrollbar py-1">
                  {/* Tools Category */}
                  {filteredSlashTools.some(t => t.category === 'tool') && (
                    <>
                      <div className="px-3 pt-2 pb-1">
                        <span className="text-[9px] font-bold uppercase tracking-[0.2em] text-emerald-500/50">🔧 System Tools</span>
                      </div>
                      {filteredSlashTools.filter(t => t.category === 'tool').map((tool) => {
                        const globalIdx = filteredSlashTools.indexOf(tool);
                        return (
                          <button
                            key={tool.id}
                            onClick={() => handleSlashSelect(tool)}
                            onMouseEnter={() => setSlashSelectedIdx(globalIdx)}
                            className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${globalIdx === slashSelectedIdx ? 'bg-emerald-500/10 text-white' : 'text-white/70 hover:bg-white/[0.04]'}`}
                          >
                            <Folder className={`w-3.5 h-3.5 flex-shrink-0 ${globalIdx === slashSelectedIdx ? 'text-emerald-400' : 'text-white/20'}`} />
                            <span className="text-sm flex-shrink-0">{tool.emoji}</span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-[13px] font-semibold">{tool.name}</span>
                                <span className="text-[10px] font-mono text-white/20">/{tool.id}</span>
                              </div>
                              <p className="text-[11px] text-white/30 truncate">{tool.description}</p>
                            </div>
                          </button>
                        );
                      })}
                    </>
                  )}
                  {/* Agents Category */}
                  {filteredSlashTools.some(t => t.category === 'agent') && (
                    <>
                      <div className="px-3 pt-3 pb-1">
                        <span className="text-[9px] font-bold uppercase tracking-[0.2em] text-violet-500/50">🤖 Agent Profiles</span>
                      </div>
                      {filteredSlashTools.filter(t => t.category === 'agent').map((tool) => {
                        const globalIdx = filteredSlashTools.indexOf(tool);
                        return (
                          <button
                            key={tool.id}
                            onClick={() => handleSlashSelect(tool)}
                            onMouseEnter={() => setSlashSelectedIdx(globalIdx)}
                            className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-colors ${globalIdx === slashSelectedIdx ? 'bg-violet-500/10 text-white' : 'text-white/70 hover:bg-white/[0.04]'}`}
                          >
                            <Folder className={`w-3.5 h-3.5 flex-shrink-0 ${globalIdx === slashSelectedIdx ? 'text-violet-400' : 'text-white/20'}`} />
                            <span className="text-sm flex-shrink-0">{tool.emoji}</span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-[13px] font-semibold">{tool.name}</span>
                                <span className="text-[10px] font-mono text-white/20">/{tool.id}</span>
                              </div>
                              <p className="text-[11px] text-white/30 truncate">{tool.description}</p>
                            </div>
                          </button>
                        );
                      })}
                    </>
                  )}
                </div>
                <div className="px-3 py-1.5 border-t border-white/5 flex items-center gap-3 text-[10px] text-white/20">
                  <span><kbd className="px-1 py-0.5 bg-white/5 rounded text-[9px]">↑↓</kbd> navigate</span>
                  <span><kbd className="px-1 py-0.5 bg-white/5 rounded text-[9px]">↵</kbd> select</span>
                  <span><kbd className="px-1 py-0.5 bg-white/5 rounded text-[9px]">esc</kbd> close</span>
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
            {/* Selected Tool Badge */}
            {selectedTool && (
              <div className="flex items-center gap-1 ml-2 px-2 py-0.5 bg-emerald-500/20 border border-emerald-500/30 rounded-full flex-shrink-0">
                <span className="text-[11px]">{selectedTool.emoji}</span>
                <span className="text-[11px] font-semibold text-emerald-400">{selectedTool.name}</span>
                <button type="button" onClick={handleRemoveTool} className="ml-0.5 p-0.5 text-emerald-400/60 hover:text-emerald-300 transition-colors rounded-full hover:bg-emerald-400/10">
                  <X className="w-2.5 h-2.5" />
                </button>
              </div>
            )}
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleInputKeyDown}
              placeholder={selectedTool ? `Ask ${selectedTool.name}...` : activeModelName ? `Ask ${activeModelName}... (type / for tools)` : 'Ask anything (type / for tools)'}
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
                  <button
                    onClick={() => {
                      setSettingsTab('mcp');
                      if (!mcpStatus) {
                        setMcpLoading(true);
                        Promise.all([
                          getMcpStatus().catch(() => null),
                          getMcpConfig('claude').catch(() => null),
                          getMcpConfig('cursor').catch(() => null),
                          getMcpConfig('vscode').catch(() => null),
                        ]).then(([status, claude, cursor, vscode]) => {
                          if (status) setMcpStatus(status);
                          setMcpConfigs({ claude, cursor, vscode });
                          setMcpLoading(false);
                        });
                      }
                    }}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${settingsTab === 'mcp'
                      ? 'bg-white/10 text-white'
                      : 'text-white/60 hover:bg-white/5 hover:text-white'
                      }`}
                  >
                    <Link2 className="w-4 h-4" />
                    MCP
                  </button>
                  <button
                    onClick={() => setSettingsTab('tokens')}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${settingsTab === 'tokens'
                      ? 'bg-white/10 text-white'
                      : 'text-white/60 hover:bg-white/5 hover:text-white'
                      }`}
                  >
                    <Flame className="w-4 h-4" />
                    Token Usage
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
                  ) : settingsTab === 'api' ? (
                    <div className="space-y-6">
                      <div>
                        <h3 className="text-lg font-medium text-white mb-1">API Configuration</h3>
                        <p className="text-sm text-white/50 mb-6">Connect your external services to power the autonomous agent.</p>
                      </div>

                      <div className="space-y-4">
                        {[
                          { name: 'OpenAI', placeholder: 'sk-proj-... (openai-5.4)', key: 'openai_api_key' as const, model: 'openai-5.4', color: 'text-green-400' },
                          { name: 'Anthropic', placeholder: 'sk-ant-... (claude-opus-4.6)', key: 'claude_api_key' as const, model: 'claude-opus-4.6', color: 'text-orange-400' },
                          { name: 'Google Gemini', placeholder: 'AIzaSy... (gemini-pro-3.1)', key: 'gemini_api_key' as const, model: 'gemini-pro-3.1', color: 'text-blue-400' },
                          { name: 'Grok (xAI)', placeholder: 'xai-... (grok-4)', key: 'grok_api_key' as const, model: 'grok-4', color: 'text-purple-400' },
                          { name: 'OpenRouter', placeholder: 'sk-or-... (openrouter)', key: 'openrouter_api_key' as const, model: 'meta-llama/llama-4-maverick', color: 'text-cyan-400' }
                        ].map((api, idx) => {
                          const liveProvider = providerList.find((p: any) => p.name === api.key.replace('_api_key', ''));
                          const isActive = liveProvider?.active;
                          const liveModel = liveProvider?.model || api.model;
                          return (
                            <div key={idx} className="space-y-1.5">
                              <div className="flex items-center justify-between">
                                <label className="text-sm font-medium text-white/80 flex items-center gap-2">
                                  {api.name}
                                  {isActive && (
                                    <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">active</span>
                                  )}
                                </label>
                                <span className={`text-[10px] font-mono ${api.color} opacity-60`}>{liveModel}</span>
                              </div>
                              <div className="relative">
                                <input
                                  type="password"
                                  placeholder={api.placeholder}
                                  value={(apiKeys as any)[api.key] || ''}
                                  onChange={(e) => setApiKeys(prev => ({ ...prev, [api.key]: e.target.value }))}
                                  className="w-full bg-[#0a0a0a] border border-white/10 focus:border-emerald-500/50 rounded-lg px-4 py-2.5 pr-28 text-white placeholder-white/20 outline-none transition-colors"
                                />
                                <span className={`absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-mono ${api.color} opacity-40 pointer-events-none`}>{api.model}</span>
                              </div>
                              {/* OpenRouter model selector */}
                              {api.key === 'openrouter_api_key' && (
                                <div className="mt-1.5">
                                  <label className="text-[11px] font-medium text-white/40 mb-1 block">Model Name</label>
                                  <input
                                    type="text"
                                    placeholder="meta-llama/llama-4-maverick"
                                    value={apiKeys.openrouter_model || ''}
                                    onChange={(e) => setApiKeys(prev => ({ ...prev, openrouter_model: e.target.value }))}
                                    className="w-full bg-[#0a0a0a] border border-white/10 focus:border-cyan-500/50 rounded-lg px-4 py-2 text-sm text-cyan-400 placeholder-white/15 outline-none transition-colors font-mono"
                                  />
                                  <p className="text-[10px] text-white/20 mt-1">Browse models at <a href="https://openrouter.ai/models" target="_blank" rel="noopener" className="text-cyan-500/60 hover:text-cyan-400 transition-colors">openrouter.ai/models</a></p>
                                </div>
                              )}
                            </div>
                          );
                        })}
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
                  ) : settingsTab === 'mcp' ? (
                    /* MCP Tab */
                    <div className="space-y-6">
                      <div>
                        <h3 className="text-lg font-medium text-white mb-1 flex items-center gap-2">
                          <Link2 className="w-5 h-5 text-cyan-400" />
                          MCP Connection
                        </h3>
                        <p className="text-sm text-white/50 mb-4">Connect Astra Agent to Claude Desktop, Cursor, VS Code, or any MCP-compatible client.</p>
                      </div>

                      {mcpLoading ? (
                        <div className="flex items-center justify-center py-12">
                          <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
                        </div>
                      ) : (
                        <>
                          {/* Connection URL */}
                          <div className="space-y-2">
                            <label className="text-xs font-bold uppercase tracking-wider text-white/40">HTTP Endpoint</label>
                            <div className="flex items-center gap-2">
                              <div className="flex-1 bg-[#0a0a0a] border border-cyan-500/20 rounded-lg px-4 py-2.5 font-mono text-sm text-cyan-400">
                                {mcpStatus?.http_url || 'http://localhost:8080/mcp'}
                              </div>
                              <button
                                onClick={() => {
                                  navigator.clipboard.writeText(mcpStatus?.http_url || 'http://localhost:8080/mcp');
                                  setMcpCopied('url');
                                  setTimeout(() => setMcpCopied(''), 2000);
                                }}
                                className="p-2.5 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/20 rounded-lg text-cyan-400 transition-colors"
                              >
                                {mcpCopied === 'url' ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                              </button>
                            </div>
                          </div>

                          {/* Client Config Picker */}
                          <div className="space-y-3">
                            <label className="text-xs font-bold uppercase tracking-wider text-white/40">Client Configuration</label>
                            <div className="flex gap-1">
                              {[
                                { key: 'claude' as const, label: 'Claude Desktop' },
                                { key: 'cursor' as const, label: 'Cursor' },
                                { key: 'vscode' as const, label: 'VS Code' },
                              ].map(({ key, label }) => (
                                <button
                                  key={key}
                                  onClick={() => setMcpSelectedClient(key)}
                                  className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${mcpSelectedClient === key
                                    ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/20'
                                    : 'text-white/30 hover:text-white/60 hover:bg-white/5'
                                    }`}
                                >
                                  {label}
                                </button>
                              ))}
                            </div>
                            <div className="relative">
                              <pre className="bg-[#0a0a0a] border border-white/10 rounded-lg p-4 text-xs font-mono text-white/70 overflow-x-auto whitespace-pre">
                                {JSON.stringify(mcpConfigs[mcpSelectedClient] || {}, null, 2)}
                              </pre>
                              <button
                                onClick={() => {
                                  navigator.clipboard.writeText(JSON.stringify(mcpConfigs[mcpSelectedClient] || {}, null, 2));
                                  setMcpCopied('config');
                                  setTimeout(() => setMcpCopied(''), 2000);
                                }}
                                className="absolute top-2 right-2 p-1.5 bg-white/5 hover:bg-white/10 rounded-md text-white/40 hover:text-white transition-colors"
                              >
                                {mcpCopied === 'config' ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>
                            </div>
                            <p className="text-[10px] text-white/25 font-mono">
                              {mcpSelectedClient === 'claude' ? 'Paste into: claude_desktop_config.json' :
                                mcpSelectedClient === 'cursor' ? 'Paste into: .cursor/mcp.json' :
                                  'Paste into: .vscode/settings.json'}
                            </p>
                          </div>

                          {/* Terminal Commands */}
                          <div className="space-y-2">
                            <label className="text-xs font-bold uppercase tracking-wider text-white/40">Server Commands</label>
                            {[
                              { label: 'stdio', cmd: mcpStatus?.stdio_command || 'python -m mcp_server' },
                              { label: 'http', cmd: mcpStatus?.http_command || 'python -m mcp_server --transport http --port 8080' },
                            ].map(({ label, cmd }) => (
                              <div key={label} className="flex items-center gap-2">
                                <span className="text-[10px] font-bold uppercase text-white/20 w-10">{label}</span>
                                <div className="flex-1 flex items-center gap-2 bg-[#0a0a0a] border border-white/10 rounded-lg px-3 py-2">
                                  <Terminal className="w-3.5 h-3.5 text-white/20 flex-shrink-0" />
                                  <code className="text-xs font-mono text-white/60 flex-1">{cmd}</code>
                                  <button
                                    onClick={() => {
                                      navigator.clipboard.writeText(cmd);
                                      setMcpCopied(label);
                                      setTimeout(() => setMcpCopied(''), 2000);
                                    }}
                                    className="p-1 text-white/20 hover:text-white/60 transition-colors"
                                  >
                                    {mcpCopied === label ? <CheckCircle2 className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>

                          {/* Available Tools */}
                          {mcpStatus?.tools && (
                            <div className="space-y-2">
                              <label className="text-xs font-bold uppercase tracking-wider text-white/40">
                                Available Tools ({mcpStatus.tools_count})
                              </label>
                              <div className="max-h-48 overflow-y-auto custom-scrollbar space-y-1">
                                {mcpStatus.tools.map((tool) => (
                                  <div key={tool.name} className="flex items-start gap-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5">
                                    <Wrench className="w-3 h-3 text-cyan-400/50 mt-0.5 flex-shrink-0" />
                                    <div>
                                      <span className="text-xs font-mono text-cyan-400/80">{tool.name}</span>
                                      <p className="text-[10px] text-white/30">{tool.description}</p>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  ) : (
                    /* Token Usage Tab */
                    (() => {
                      const totalTokensUsed = tokenRecords.reduce((a, r) => a + r.totalTokens, 0);
                      const totalPrompt = tokenRecords.reduce((a, r) => a + r.promptTokens, 0);
                      const totalCompletion = tokenRecords.reduce((a, r) => a + r.completionTokens, 0);
                      const burnPercent = Math.min(100, (totalTokensUsed / tokenBudget) * 100);
                      const circumference = 2 * Math.PI * 45;
                      const burnDash = circumference * (burnPercent / 100);

                      // Provider breakdown
                      const providerBreakdown: Record<string, { count: number; tokens: number }> = {};
                      tokenRecords.forEach(r => {
                        if (!providerBreakdown[r.provider]) providerBreakdown[r.provider] = { count: 0, tokens: 0 };
                        providerBreakdown[r.provider].count++;
                        providerBreakdown[r.provider].tokens += r.totalTokens;
                      });

                      return (
                        <div className="space-y-6 flex flex-col h-full">
                          <div>
                            <h3 className="text-lg font-medium text-white mb-1 flex items-center gap-2">
                              <Flame className="w-5 h-5 text-orange-400" />
                              Token Usage
                            </h3>
                            <p className="text-sm text-white/50 mb-4">Monitor token consumption across all requests. Estimated at ~4 characters per token.</p>
                          </div>

                          {/* Summary Cards + Ring */}
                          <div className="flex gap-4 items-center">
                            {/* Ring Chart */}
                            <div className="relative flex-shrink-0">
                              <svg width="110" height="110" className="-rotate-90">
                                <circle cx="55" cy="55" r="45" stroke="rgba(255,255,255,0.05)" strokeWidth="8" fill="none" />
                                <circle
                                  cx="55" cy="55" r="45"
                                  stroke={burnPercent > 90 ? '#ef4444' : burnPercent > 70 ? '#f59e0b' : '#10b981'}
                                  strokeWidth="8" fill="none"
                                  strokeDasharray={`${burnDash} ${circumference - burnDash}`}
                                  strokeLinecap="round"
                                  style={{ transition: 'stroke-dasharray 0.5s ease, stroke 0.3s ease' }}
                                />
                              </svg>
                              <div className="absolute inset-0 flex flex-col items-center justify-center">
                                <span className={`text-lg font-black ${burnPercent > 90 ? 'text-red-400' : burnPercent > 70 ? 'text-amber-400' : 'text-emerald-400'}`}>
                                  {burnPercent.toFixed(1)}%
                                </span>
                                <span className="text-[9px] text-white/30 font-mono">BURNED</span>
                              </div>
                            </div>

                            {/* Stats Grid */}
                            <div className="flex-1 grid grid-cols-2 gap-2">
                              <div className="bg-gradient-to-br from-orange-500/10 to-orange-500/5 border border-orange-500/15 rounded-xl p-3">
                                <div className="text-[10px] font-bold uppercase tracking-wider text-orange-400/60 mb-1">Total Tokens</div>
                                <div className="text-xl font-black text-orange-400 tabular-nums">{totalTokensUsed.toLocaleString()}</div>
                              </div>
                              <div className="bg-gradient-to-br from-violet-500/10 to-violet-500/5 border border-violet-500/15 rounded-xl p-3">
                                <div className="text-[10px] font-bold uppercase tracking-wider text-violet-400/60 mb-1">Prompt</div>
                                <div className="text-xl font-black text-violet-400 tabular-nums">{totalPrompt.toLocaleString()}</div>
                              </div>
                              <div className="bg-gradient-to-br from-cyan-500/10 to-cyan-500/5 border border-cyan-500/15 rounded-xl p-3">
                                <div className="text-[10px] font-bold uppercase tracking-wider text-cyan-400/60 mb-1">Completion</div>
                                <div className="text-xl font-black text-cyan-400 tabular-nums">{totalCompletion.toLocaleString()}</div>
                              </div>
                              <div className="bg-gradient-to-br from-emerald-500/10 to-emerald-500/5 border border-emerald-500/15 rounded-xl p-3">
                                <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-400/60 mb-1">Requests</div>
                                <div className="text-xl font-black text-emerald-400 tabular-nums">{tokenRecords.length}</div>
                              </div>
                            </div>
                          </div>

                          {/* Budget Bar */}
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <label className="text-xs font-bold uppercase tracking-wider text-white/40">Token Budget</label>
                              <div className="flex items-center gap-2">
                                <input
                                  type="number"
                                  value={tokenBudget}
                                  onChange={e => setTokenBudget(Math.max(1000, Number(e.target.value)))}
                                  className="w-28 bg-[#0a0a0a] border border-white/10 rounded-lg px-3 py-1.5 text-xs font-mono text-white/70 text-right outline-none focus:border-orange-500/40 transition-colors"
                                />
                                <span className="text-[10px] text-white/20">tokens</span>
                              </div>
                            </div>
                            <div className="h-3 bg-white/5 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all duration-500 ${burnPercent > 90 ? 'bg-gradient-to-r from-red-500 to-red-400' : burnPercent > 70 ? 'bg-gradient-to-r from-amber-500 to-amber-400' : 'bg-gradient-to-r from-emerald-500 to-emerald-400'}`}
                                style={{ width: `${burnPercent}%` }}
                              />
                            </div>
                            <div className="flex justify-between text-[10px] font-mono text-white/20">
                              <span>{totalTokensUsed.toLocaleString()} used</span>
                              <span>{(tokenBudget - totalTokensUsed).toLocaleString()} remaining</span>
                            </div>
                          </div>

                          {/* Provider Breakdown & Request History flex container */}
                          <div className="flex-1 flex flex-col gap-6 min-h-0">
                            {/* Provider Breakdown */}
                            {Object.keys(providerBreakdown).length > 0 && (
                              <div className="space-y-2 flex-shrink-0">
                                <label className="text-xs font-bold uppercase tracking-wider text-white/40">By Provider</label>
                                <div className="space-y-1.5 max-h-[80px] overflow-y-auto custom-scrollbar">
                                  {Object.entries(providerBreakdown).sort((a, b) => b[1].tokens - a[1].tokens).map(([provider, data]) => (
                                    <div key={provider} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/5">
                                      <Zap className="w-3.5 h-3.5 text-amber-400/50 flex-shrink-0" />
                                      <span className="text-[11px] font-bold text-white/60 w-32 truncate flex-shrink-0">{provider}</span>
                                      <div className="flex-1 min-w-[50px] h-1.5 bg-white/5 rounded-full overflow-hidden">
                                        <div className="h-full bg-amber-500/40 rounded-full" style={{ width: `${(data.tokens / totalTokensUsed) * 100}%` }} />
                                      </div>
                                      <span className="text-[10px] font-mono text-white/30 w-16 text-right flex-shrink-0">{data.tokens.toLocaleString()} tk</span>
                                      <span className="text-[10px] font-mono text-white/15 w-8 text-right flex-shrink-0">{data.count}×</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Per-Request History */}
                            <div className="space-y-2 flex-1 min-h-0 flex flex-col pb-4">
                              <div className="flex items-center justify-between flex-shrink-0">
                                <label className="text-xs font-bold uppercase tracking-wider text-white/40">Request History</label>
                                {tokenRecords.length > 0 && (
                                  <button
                                    onClick={() => setTokenRecords([])}
                                    className="text-[10px] text-red-400/50 hover:text-red-400 transition-colors font-bold uppercase tracking-wider"
                                  >
                                    Clear All
                                  </button>
                                )}
                              </div>

                              <div className="flex-1 overflow-y-auto custom-scrollbar space-y-1 -mr-2 pr-2">
                                {tokenRecords.length === 0 ? (
                                  <div className="flex flex-col items-center justify-center py-8 text-white/15 h-full">
                                    <Flame className="w-8 h-8 mb-3" />
                                    <span className="text-sm">No tokens burned yet</span>
                                    <span className="text-xs mt-1">Send a message to start tracking</span>
                                  </div>
                                ) : (
                                  tokenRecords.map((record) => {
                                    const maxTk = Math.max(...tokenRecords.map(r => r.totalTokens), 1);
                                    const barWidth = Math.max(2, (record.totalTokens / maxTk) * 100);
                                    return (
                                      <div key={record.id} className="relative flex items-center gap-3 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5 hover:border-white/10 transition-colors group overflow-hidden">
                                        {/* Background bar */}
                                        <div
                                          className="absolute left-0 top-0 h-full bg-gradient-to-r from-orange-500/[0.08] to-transparent transition-all"
                                          style={{ width: `${barWidth}%` }}
                                        />
                                        {/* Content */}
                                        <div className="relative flex items-center gap-3 w-full">
                                          <div className="flex flex-col items-center w-12 flex-shrink-0">
                                            <span className="text-[11px] font-black text-orange-400/80 tabular-nums">{record.totalTokens}</span>
                                            <span className="text-[8px] text-white/15 font-mono">tokens</span>
                                          </div>
                                          <div className="flex-1 min-w-0">
                                            <p className="text-[11px] text-white/60 truncate">{record.message || '(empty)'}</p>
                                            <div className="flex items-center gap-2 mt-0.5">
                                              <span className="text-[9px] font-mono text-violet-400/40">{record.promptTokens} in</span>
                                              <span className="text-[9px] text-white/10">→</span>
                                              <span className="text-[9px] font-mono text-cyan-400/40">{record.completionTokens} out</span>
                                            </div>
                                          </div>
                                          <div className="flex flex-col items-end flex-shrink-0">
                                            <span className="text-[9px] font-mono text-white/20 max-w-[80px] truncate">{record.provider}</span>
                                            <span className="text-[8px] font-mono text-white/10">{record.timestamp.toLocaleTimeString()}</span>
                                          </div>
                                        </div>
                                      </div>
                                    );
                                  })
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })()
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

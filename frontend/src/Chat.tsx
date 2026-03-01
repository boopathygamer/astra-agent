import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  SquarePen,
  GraduationCap,
  Code,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  FileText,
  BrainCircuit,
  Image as ImageIcon,
  Bot,
  Smartphone,
  Cpu,
  Plus,
  Mic,
  UserPlus,
  RefreshCcw,
  ChevronDown,
  ChevronUp,
  Loader2,
  Wifi,
  WifiOff,
  Clock,
  Zap,
  Settings,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { chatStream, chatSync, getHealth, type StreamChunk, type HealthResponse } from './services/api';
import SettingsModal from './SettingsModal';
import { useAgentStore } from './store/useAgentStore';

// ── Types ────────────────────────────────────────

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  isStreaming?: boolean;
  confidence?: number;
  mode?: string;
  tools_used?: string[];
  thinking_steps?: string[];
  duration_ms?: number;
  iterations?: number;
}

// ── Logo ─────────────────────────────────────────

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

// ── Thinking Steps Panel ─────────────────────────

const ThinkingPanel = ({ message }: { message: Message }) => {
  const [isOpen, setIsOpen] = useState(false);
  if (!message.thinking_steps?.length && !message.tools_used?.length && !message.confidence) return null;

  return (
    <div className="mt-3 border-t border-white/5 pt-3">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 text-xs text-white/30 hover:text-white/50 transition-colors"
      >
        {isOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        <span className="font-mono uppercase tracking-wider">
          {message.mode || 'direct'} · {message.confidence ? `${(message.confidence * 100).toFixed(0)}% conf` : ''}
          {message.duration_ms ? ` · ${(message.duration_ms / 1000).toFixed(1)}s` : ''}
          {message.iterations ? ` · ${message.iterations} iter` : ''}
        </span>
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            {message.thinking_steps && message.thinking_steps.length > 0 && (
              <div className="mt-2 space-y-1">
                <span className="text-[10px] uppercase tracking-widest text-emerald-500/60 font-bold">Thinking</span>
                {message.thinking_steps.map((step, i) => (
                  <div key={i} className="text-xs text-white/40 font-mono pl-3 border-l border-emerald-500/20">
                    {step}
                  </div>
                ))}
              </div>
            )}
            {message.tools_used && message.tools_used.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                <span className="text-[10px] uppercase tracking-widest text-emerald-500/60 font-bold mr-1">Tools</span>
                {message.tools_used.map((tool, i) => (
                  <span key={i} className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] rounded-full font-mono">
                    {tool}
                  </span>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// ── Main Chat Component ──────────────────────────

export default function Chat() {
  const [isSidebarOpen, setSidebarOpen] = useState(window.innerWidth >= 768);
  const [isPlusMenuOpen, setPlusMenuOpen] = useState(false);
  const [isSettingsOpen, setSettingsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [elapsedTime, setElapsedTime] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const plusMenuRef = useRef<HTMLDivElement>(null);
  const conversationIdRef = useRef<string>(`conv-${Date.now()}`);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const addActivity = useAgentStore(state => state.addActivity);

  // ── Health check ─────────────────────────────
  useEffect(() => {
    const checkHealth = async () => {
      try {
        await getHealth();
        setBackendStatus('online');
      } catch {
        setBackendStatus('offline');
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  // ── Responsive sidebar ───────────────────────
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 768) setSidebarOpen(false);
      else setSidebarOpen(true);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // ── Auto-scroll ──────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Close plus menu on click outside ─────────
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (plusMenuRef.current && !plusMenuRef.current.contains(event.target as Node)) {
        setPlusMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ── Elapsed timer ────────────────────────────
  useEffect(() => {
    if (isLoading) {
      setElapsedTime(0);
      timerRef.current = setInterval(() => setElapsedTime(t => t + 0.1), 100);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isLoading]);

  // ── Send message ─────────────────────────────
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      text: input.trim(),
      isUser: true,
    };

    const assistantId = `ai-${Date.now()}`;
    const assistantMsg: Message = {
      id: assistantId,
      text: '',
      isUser: false,
      isStreaming: true,
    };

    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setInput('');
    setIsLoading(true);

    addActivity('user', 'Chat Input Received', input.trim());
    addActivity('thinking', 'Agent Invoked', 'Processing chat message...');

    try {
      // Try SSE streaming first
      let fullText = '';
      let usedFallback = false;

      try {
        for await (const chunk of chatStream(input.trim(), conversationIdRef.current)) {
          if (chunk.type === 'text') {
            fullText += chunk.content;
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId ? { ...m, text: fullText } : m
              )
            );
          } else if (chunk.type === 'done') {
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? {
                    ...m,
                    text: fullText || m.text,
                    isStreaming: false,
                    duration_ms: (chunk.meta?.duration_ms as number) || undefined,
                  }
                  : m
              )
            );
          } else if (chunk.type === 'error') {
            throw new Error(chunk.content);
          }
        }

        addActivity('result', 'Chat Response Streaming Completed', fullText);
      } catch (streamErr) {
        // Fallback to sync chat
        usedFallback = true;
        try {
          const rawResult = await chatSync(input.trim(), conversationIdRef.current) as any;

          let result: any;
          if (typeof rawResult === 'string') {
            result = { answer: `⚠️ ${rawResult}` };
            fullText = result.answer;
          } else {
            result = rawResult;
            fullText = result.answer || 'No response from server';
          }

          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? {
                  ...m,
                  text: fullText,
                  isStreaming: false,
                  confidence: result.confidence,
                  mode: result.mode,
                  tools_used: result.tools_used,
                  thinking_steps: result.thinking_steps,
                  duration_ms: result.duration_ms,
                  iterations: result.iterations,
                }
                : m
            )
          );

          if (result.tools_used && result.tools_used.length > 0) {
            result.tools_used.forEach((t: any) => {
              const toolName = typeof t === 'string' ? t : t.tool || 'Unknown Tool';
              const toolResult = typeof t === 'string' ? 'Executed successfully' : t.result || 'Executed successfully';
              addActivity('tool', `Tool Execution: ${toolName}`, toolResult);
            });
          }
          if (result.thinking_steps) {
            result.thinking_steps.forEach((step, i) => {
              addActivity('thinking', `Reasoning Iteration ${i + 1}`, `${step}`);
            });
          }
          addActivity(
            'result',
            'Chat Response Generated',
            result.answer,
            {
              confidence: result.confidence,
              durationMs: result.duration_ms,
              mode: result.mode,
              iterations: result.iterations
            }
          );
        } catch (syncErr) {
          const errMsg = syncErr instanceof Error ? syncErr.message : 'Connection failed';
          addActivity('error', 'Chat Request Failed', errMsg);
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? {
                  ...m,
                  text: `⚠️ Could not reach the Super System backend. Make sure the server is running:\n\n\`cd backend && python main.py server\`\n\nError: ${errMsg}`,
                  isStreaming: false,
                }
                : m
            )
          );
        }
      }

      // Mark streaming complete if not already done
      if (!usedFallback) {
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId && m.isStreaming
              ? { ...m, isStreaming: false, text: fullText || 'No response generated.' }
              : m
          )
        );
      }
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading]);

  // ── Status indicator ─────────────────────────
  const StatusDot = () => (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/5">
      {backendStatus === 'online' ? (
        <Wifi className="w-3.5 h-3.5 text-emerald-400" />
      ) : backendStatus === 'offline' ? (
        <WifiOff className="w-3.5 h-3.5 text-red-400" />
      ) : (
        <Loader2 className="w-3.5 h-3.5 text-yellow-400 animate-spin" />
      )}
      <span className="text-[10px] font-mono uppercase tracking-widest text-white/40">
        {backendStatus === 'online' ? 'Connected' : backendStatus === 'offline' ? 'Offline' : 'Checking'}
      </span>
    </div>
  );

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
                <div className="w-8 h-8 rounded-full bg-white/10 border border-white/20 flex items-center justify-center">
                  <Settings className="w-4 h-4 text-white/70" />
                </div>
                <div className="flex flex-col items-start">
                  <span className="font-medium">Settings</span>
                  <span className="text-xs text-white/40">Account & API Keys</span>
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
              <Zap className="w-4 h-4 text-emerald-400" />
              Autonomous Agent
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusDot />
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
              <h1 className="text-3xl font-medium mb-4 text-white tracking-tight">What are you working on?</h1>
              <p className="text-sm text-white/30 max-w-md text-center">
                {backendStatus === 'online'
                  ? 'Connected to Super System — full AI power ready.'
                  : 'Start the backend with `python main.py server` for full power.'}
              </p>
            </div>
          ) : (
            <div className="flex-1 w-full max-w-3xl mx-auto px-4 py-8 space-y-8">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.isUser ? 'justify-end' : 'justify-start'}`}>
                  {msg.isUser ? (
                    <div className="max-w-[80%] rounded-2xl px-4 py-2.5 bg-[#2f2f2f] text-white/90 border border-white/5 shadow-sm">
                      <div className="whitespace-pre-wrap leading-relaxed text-sm">
                        {msg.text}
                      </div>
                    </div>
                  ) : (
                    <div className="max-w-[85%] flex gap-4">
                      <div className="w-8 h-8 rounded-full bg-white/10 border border-white/20 flex items-center justify-center flex-shrink-0 mt-1">
                        {msg.isStreaming ? (
                          <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
                        ) : (
                          <CustomLogo className="w-5 h-5 text-white" />
                        )}
                      </div>
                      <div className="pt-1.5 text-white/90 flex-1 min-w-0">
                        <div className="whitespace-pre-wrap leading-relaxed break-words">
                          {msg.text}
                          {msg.isStreaming && (
                            <span className="inline-block w-2 h-5 bg-emerald-400 ml-0.5 animate-pulse rounded-sm" />
                          )}
                        </div>
                        {!msg.isStreaming && <ThinkingPanel message={msg} />}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-center justify-center gap-2 py-2 text-xs text-white/30">
            <Clock className="w-3 h-3" />
            <span className="font-mono">{elapsedTime.toFixed(1)}s</span>
          </div>
        )}

        {/* Input Area */}
        <div className="p-4 w-full max-w-3xl mx-auto relative">
          <AnimatePresence>
            {isPlusMenuOpen && (
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className="absolute bottom-[calc(100%-1rem)] left-4 bg-[#2f2f2f] border border-white/10 rounded-xl p-1 shadow-xl z-50 w-48"
                ref={plusMenuRef}
              >
                <div className="flex flex-col gap-0">
                  <button
                    className="flex items-center gap-2 px-3 py-2 text-sm text-white/90 hover:bg-white/10 rounded-lg transition-colors w-full text-left"
                    onClick={() => setPlusMenuOpen(false)}
                  >
                    <Cpu className="w-4 h-4 text-emerald-400" />
                    Core Agent
                  </button>
                  <button
                    className="flex items-center gap-2 px-3 py-2 text-sm text-white/90 hover:bg-white/10 rounded-lg transition-colors w-full text-left"
                    onClick={() => setPlusMenuOpen(false)}
                  >
                    <ImageIcon className="w-4 h-4 text-emerald-400" />
                    Images
                  </button>
                  <button
                    className="flex items-center gap-2 px-3 py-2 text-sm text-white/90 hover:bg-white/10 rounded-lg transition-colors w-full text-left"
                    onClick={() => setPlusMenuOpen(false)}
                  >
                    <FileText className="w-4 h-4 text-emerald-400" />
                    Files
                  </button>
                  <button
                    className="flex items-center gap-2 px-3 py-2 text-sm text-white/90 hover:bg-white/10 rounded-lg transition-colors w-full text-left"
                    onClick={() => setPlusMenuOpen(false)}
                  >
                    <BrainCircuit className="w-4 h-4 text-emerald-400" />
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
              placeholder={isLoading ? "AI is processing..." : "Ask anything"}
              disabled={isLoading}
              className="flex-1 bg-transparent border-none outline-none px-3 text-white placeholder-white/30 text-base disabled:opacity-50"
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
                <button
                  type="submit"
                  disabled={isLoading}
                  className="p-2 bg-emerald-500 text-black rounded-full hover:bg-emerald-400 transition-colors shadow-[0_0_10px_rgba(16,185,129,0.3)] disabled:opacity-50"
                >
                  {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                </button>
              )}
            </div>
          </form>
          <div className="text-center mt-3 text-xs text-white/30">
            Astra Agent · Powered by Super System · Full Autonomous AI
          </div>
        </div>
      </div>

      {/* Settings Modal */}
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

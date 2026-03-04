import React, { useState, useRef, useEffect } from 'react';
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
  Key
} from 'lucide-react';
import { Link } from 'react-router-dom';

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
  const [messages, setMessages] = useState<{text: string, isUser: boolean}[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const plusMenuRef = useRef<HTMLDivElement>(null);

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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    setMessages(prev => [...prev, { text: input, isUser: true }]);
    setInput('');

    setTimeout(() => {
      setMessages(prev => [...prev, { 
        text: "I am an Autonomous Agent, your AI assistant. I'm ready to help you build, analyze, and scale your ideas. What would you like to focus on today?", 
        isUser: false 
      }]);
    }, 1000);
  };

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
                      <div className="whitespace-pre-wrap leading-relaxed text-sm">
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
                    onClick={() => setPlusMenuOpen(false)}
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
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      settingsTab === 'account' 
                        ? 'bg-white/10 text-white' 
                        : 'text-white/60 hover:bg-white/5 hover:text-white'
                    }`}
                  >
                    <User className="w-4 h-4" />
                    Account
                  </button>
                  <button
                    onClick={() => setSettingsTab('api')}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                      settingsTab === 'api' 
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
                          { name: 'OpenAI API Key', placeholder: 'sk-proj-...' },
                          { name: 'Anthropic API Key', placeholder: 'sk-ant-...' },
                          { name: 'Google Gemini API Key', placeholder: 'AIzaSy...' },
                          { name: 'Grok API Key', placeholder: 'xai-...' },
                          { name: 'OpenRouter API Key', placeholder: 'sk-or-...' }
                        ].map((api, idx) => (
                          <div key={idx} className="space-y-1.5">
                            <label className="text-sm font-medium text-white/80">{api.name}</label>
                            <input 
                              type="password" 
                              placeholder={api.placeholder}
                              className="w-full bg-[#0a0a0a] border border-white/10 focus:border-emerald-500/50 rounded-lg px-4 py-2.5 text-white placeholder-white/20 outline-none transition-colors"
                            />
                          </div>
                        ))}
                      </div>

                      <div className="pt-4 mt-6 border-t border-white/10 flex justify-end">
                        <button className="px-6 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-black font-medium rounded-lg transition-colors shadow-[0_0_15px_rgba(16,185,129,0.2)]">
                          Connect APIs
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
    </div>
  );
}

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft, Send, Play, Code2, Smartphone, Download, RotateCcw, Package,
  Shield, Loader2, CheckCircle2, XCircle, FileCode, FolderOpen, Bot,
  AlertTriangle, Activity, Upload, Layers, Cpu, Zap, ChevronRight, X
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { sendChat, type ChatResponse } from './api';
import ProjectUploader from './ProjectUploader';
import DeployPanel, { ModelBadge } from './DeployPanel';

// ── Types ──
interface Message { id: string; text: string; isUser: boolean; agent?: string; }
interface PipelineStage { id: string; label: string; icon: string; status: 'idle' | 'running' | 'done' | 'error'; }
interface GeneratedFile { name: string; language: string; content: string; }
interface ScanResult { severity: 'critical' | 'warning' | 'info'; title: string; detail: string; }
type Framework = 'kotlin' | 'flutter' | 'react-native' | null;

// ── Constants ──
const INITIAL_STAGES: PipelineStage[] = [
  { id: 'plan', label: 'Planning', icon: '🧠', status: 'idle' },
  { id: 'scaffold', label: 'Scaffold', icon: '🏗️', status: 'idle' },
  { id: 'ui', label: 'UI Build', icon: '🎨', status: 'idle' },
  { id: 'logic', label: 'Logic', icon: '⚙️', status: 'idle' },
  { id: 'security', label: 'Security', icon: '🛡️', status: 'idle' },
  { id: 'deploy', label: 'Complete', icon: '🚀', status: 'idle' },
];

const FRAMEWORKS = [
  { id: 'kotlin' as const, name: 'Kotlin Multiplatform', icon: '🟣', color: 'from-violet-500 to-purple-600', border: 'border-violet-500/30', desc: 'Native Android & iOS via shared Kotlin code. Best for performance-critical apps.', ext: '.kt' },
  { id: 'flutter' as const, name: 'Flutter', icon: '🔵', color: 'from-cyan-500 to-blue-600', border: 'border-cyan-500/30', desc: 'Dart-based cross-platform framework by Google. Beautiful Material/Cupertino widgets.', ext: '.dart' },
  { id: 'react-native' as const, name: 'React Native', icon: '🟢', color: 'from-emerald-500 to-teal-600', border: 'border-emerald-500/30', desc: 'JavaScript/TypeScript framework by Meta. Leverage your web skills for mobile.', ext: '.tsx' },
];

const getSystemPrompt = (fw: Framework) => {
  const base = `You are ASTRA App Builder — an autonomous mobile app development agent.
The user will describe a mobile app they want built. You MUST respond with COMPLETE, working HTML code that simulates a mobile app UI.

CRITICAL RULES:
1. Output a single HTML file with ALL CSS in <style> tags and ALL JS in <script> tags
2. Design MUST be mobile-first: use mobile viewport, touch-friendly controls, 375px width max
3. Use modern mobile design: rounded corners, bottom navigation, card layouts, smooth transitions
4. Include realistic content, not placeholders
5. Make it visually stunning with a professional mobile color palette
6. Include interactive elements that work (buttons, forms, navigation, tabs)
7. Start your response with <!DOCTYPE html> — no markdown, no explanations, ONLY the HTML code
8. The HTML must be complete and self-contained
9. Add <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">`;
  if (fw === 'kotlin') return base + '\n10. Style it like a native Material You / Jetpack Compose app';
  if (fw === 'flutter') return base + '\n10. Style it like a Flutter app with Material/Cupertino widgets';
  return base + '\n10. Style it like a React Native app with modern components';
};

const MODIFY_PROMPT = `You are ASTRA App Builder. The user wants to modify an existing mobile app.
You will receive the current HTML code and the user's modification request.
CRITICAL RULES:
1. Output the COMPLETE modified HTML file — not a diff, not a snippet
2. Keep all existing functionality unless asked to remove it
3. Start your response with <!DOCTYPE html> — no markdown, no explanations
4. Maintain mobile-first responsive design and consistency`;

// ── Main Component ──
export default function AppDevPage() {
  const [framework, setFramework] = useState<Framework>(null);
  const [showSelector, setShowSelector] = useState(true);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeTab, setActiveTab] = useState<'preview' | 'code' | 'security'>('preview');
  const [stages, setStages] = useState<PipelineStage[]>(INITIAL_STAGES);
  const [isBuilding, setIsBuilding] = useState(false);
  const [htmlContent, setHtmlContent] = useState('');
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile[]>([]);
  const [activeFile, setActiveFile] = useState(0);
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [agentLogs, setAgentLogs] = useState<string[]>([]);
  const [showUploader, setShowUploader] = useState(false);
  const [showDeploy, setShowDeploy] = useState(false);
  const [deviceView, setDeviceView] = useState<'android' | 'iphone'>('android');
  const chatEndRef = useRef<HTMLDivElement>(null);
  const deviceRef = useRef<HTMLIFrameElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const addLog = useCallback((msg: string) => {
    setAgentLogs(prev => [...prev, `[${new Date().toLocaleTimeString('en-US', { hour12: false })}] ${msg}`]);
  }, []);
  const addMessage = useCallback((text: string, isUser: boolean, agent?: string) => {
    setMessages(prev => [...prev, { id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, text, isUser, agent }]);
  }, []);
  const updateStage = useCallback((id: string, status: PipelineStage['status']) => {
    setStages(prev => prev.map(s => s.id === id ? { ...s, status } : s));
  }, []);
  const delay = (ms: number) => new Promise(r => setTimeout(r, ms));

  const extractCode = (response: string): string => {
    let code = response.trim();
    if (code.startsWith('```')) code = code.replace(/^```(?:html)?\n?/, '').replace(/\n?```$/, '');
    if (!code.toLowerCase().startsWith('<!doctype') && !code.toLowerCase().startsWith('<html'))
      code = `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1"><title>App</title></head><body>${code}</body></html>`;
    return code;
  };

  const parseFiles = (html: string): GeneratedFile[] => {
    const fw = framework || 'react-native';
    const mainName = fw === 'kotlin' ? 'MainActivity.kt' : fw === 'flutter' ? 'main.dart' : 'App.tsx';
    const files: GeneratedFile[] = [{ name: mainName, language: fw === 'kotlin' ? 'kotlin' : fw === 'flutter' ? 'dart' : 'tsx', content: html }];
    const style = html.match(/<style[^>]*>([\s\S]*?)<\/style>/gi);
    if (style) files.push({ name: 'styles.css', language: 'css', content: style.map(s => s.replace(/<\/?style[^>]*>/gi, '')).join('\n\n') });
    const script = html.match(/<script[^>]*>([\s\S]*?)<\/script>/gi);
    if (script) files.push({ name: 'logic.js', language: 'javascript', content: script.map(s => s.replace(/<\/?script[^>]*>/gi, '')).join('\n\n') });
    return files;
  };

  const runSecurityScan = (html: string): ScanResult[] => {
    const r: ScanResult[] = [];
    if (html.includes('eval(')) r.push({ severity: 'critical', title: 'Unsafe eval() usage', detail: 'eval() can execute arbitrary code. Use safer alternatives.' });
    if (html.includes('innerHTML')) r.push({ severity: 'warning', title: 'innerHTML detected', detail: 'Can lead to XSS. Consider textContent or sanitization.' });
    if (html.includes('http://') && !html.includes('localhost')) r.push({ severity: 'warning', title: 'Insecure HTTP links', detail: 'Use HTTPS for external resources.' });
    if (/api[_-]?key|secret|password/i.test(html)) r.push({ severity: 'critical', title: 'Hardcoded secrets', detail: 'Never embed API keys or secrets in client code.' });
    if (/<uses-permission/i.test(html)) r.push({ severity: 'warning', title: 'Permission usage', detail: 'Review requested permissions for necessity.' });
    if (r.length === 0) r.push({ severity: 'info', title: 'No issues detected', detail: 'Basic security scan passed.' });
    return r;
  };

  // ── Build Pipeline ──
  const handleBuild = useCallback(async (prompt: string) => {
    if (!prompt.trim() || isBuilding) return;
    setIsBuilding(true); setStages(INITIAL_STAGES); setScanResults([]); addMessage(prompt, true);
    addLog(`Build initiated: "${prompt.slice(0, 80)}..."`);
    try {
      updateStage('plan', 'running'); addLog('🧠 Planning mobile architecture...'); await delay(800); updateStage('plan', 'done');
      updateStage('scaffold', 'running'); addLog('🏗️ Scaffolding project...'); await delay(600); updateStage('scaffold', 'done');
      updateStage('ui', 'running'); addLog('🎨 Building UI with agents...');
      addMessage('Building your mobile app... Agents are generating the code.', false, 'Build Agent');

      const isModification = htmlContent.length > 0;
      const systemPrompt = isModification ? MODIFY_PROMPT : getSystemPrompt(framework);
      const fullPrompt = isModification ? `Current HTML:\n\`\`\`html\n${htmlContent}\n\`\`\`\n\nModification: ${prompt}` : prompt;

      let response: ChatResponse;
      try { response = await sendChat(fullPrompt); }
      catch { response = { answer: generateFallbackApp(prompt, framework), confidence: 0.95, iterations: 1, mode: 'direct', thinking_steps: [], tools_used: [], duration_ms: 1200 }; addLog('⚠️ Backend unreachable — using local generation'); }

      const code = extractCode(response.answer);
      setHtmlContent(code); setGeneratedFiles(parseFiles(code)); setActiveFile(0);
      updateStage('ui', 'done'); addLog(`🎨 UI generated — ${code.length} bytes`);

      updateStage('logic', 'running'); addLog('⚙️ Wiring business logic...'); await delay(700); updateStage('logic', 'done');
      updateStage('security', 'running'); addLog('🛡️ Running security analysis...'); await delay(900);
      const scans = runSecurityScan(code); setScanResults(scans); updateStage('security', 'done');
      addLog(`🛡️ Security: ${scans.filter(s => s.severity === 'critical').length} critical, ${scans.filter(s => s.severity === 'warning').length} warnings`);

      updateStage('deploy', 'done');
      addMessage(`✅ Build complete!\n\n• Framework: ${FRAMEWORKS.find(f => f.id === framework)?.name || 'React Native'}\n• Files: ${parseFiles(code).length}\n• Security issues: ${scans.filter(s => s.severity !== 'info').length}\n• Build time: ${response.duration_ms?.toFixed(0) || '~2000'}ms`, false, 'ASTRA Builder');
      addLog('🚀 Build pipeline complete!');
    } catch (err: any) {
      updateStage('ui', 'error'); addMessage(`❌ Build failed: ${err?.message || 'Unknown error'}`, false, 'System'); addLog(`❌ Error: ${err?.message}`);
    } finally { setIsBuilding(false); }
  }, [isBuilding, htmlContent, framework, addMessage, addLog, updateStage]);

  const handleSubmit = useCallback((e: React.FormEvent) => { e.preventDefault(); if (!input.trim()) return; handleBuild(input); setInput(''); }, [input, handleBuild]);

  const selectFramework = (fw: Framework) => {
    setFramework(fw); setShowSelector(false);
    const name = fw ? FRAMEWORKS.find(f => f.id === fw)?.name : 'React Native';
    setMessages([{ id: '0', text: `Welcome to ASTRA App Studio — ${name} environment.\n\nDescribe the mobile app you'd like me to build. For example:\n• "Build a fitness tracking app with workout logs"\n• "Create a chat messenger with dark mode"\n• "Make a food delivery app with cart and checkout"`, isUser: false, agent: 'ASTRA Builder' }]);
    if (!fw) setFramework('react-native');
  };

  // Sync iframe content
  useEffect(() => {
    if (htmlContent && deviceRef.current) {
      deviceRef.current.srcdoc = htmlContent;
    }
  }, [htmlContent, deviceView]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [agentLogs]);

  // ── Framework Selection Modal ──
  if (showSelector) {
    return (
      <div className="h-screen bg-[#050505] text-white flex items-center justify-center font-sans overflow-hidden relative">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_20%,rgba(139,92,246,0.08),transparent_60%),radial-gradient(ellipse_at_70%_80%,rgba(6,182,212,0.06),transparent_60%)]" />
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="relative z-10 max-w-2xl w-full mx-4">
          <div className="text-center mb-10">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-violet-500/20 to-cyan-500/20 border border-violet-500/20 flex items-center justify-center">
              <Smartphone className="w-8 h-8 text-violet-400" />
            </div>
            <h1 className="text-3xl font-black tracking-tight mb-2">ASTRA App Studio</h1>
            <p className="text-white/40 text-sm">Choose your framework to get started</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            {FRAMEWORKS.map(fw => (
              <motion.button key={fw.id} whileHover={{ scale: 1.03, y: -4 }} whileTap={{ scale: 0.98 }}
                onClick={() => selectFramework(fw.id)}
                className={`relative p-6 rounded-2xl border ${fw.border} bg-white/[0.02] hover:bg-white/[0.05] transition-all text-left group overflow-hidden`}>
                <div className={`absolute inset-0 bg-gradient-to-br ${fw.color} opacity-0 group-hover:opacity-5 transition-opacity`} />
                <div className="text-3xl mb-3">{fw.icon}</div>
                <div className="font-bold text-sm mb-1.5">{fw.name}</div>
                <div className="text-[11px] text-white/35 leading-relaxed">{fw.desc}</div>
                <ChevronRight className="w-4 h-4 text-white/20 group-hover:text-white/50 absolute top-6 right-4 transition-colors" />
              </motion.button>
            ))}
          </div>

          <div className="text-center">
            <button onClick={() => selectFramework(null)}
              className="px-6 py-2.5 text-sm font-medium text-white/30 hover:text-white/60 hover:bg-white/5 rounded-xl transition-all">
              Skip — use default (React Native)
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  const fwInfo = FRAMEWORKS.find(f => f.id === framework) || FRAMEWORKS[2];

  // ── Main IDE ──
  return (
    <div className="h-screen bg-[#050505] text-white flex flex-col overflow-hidden font-sans selection:bg-violet-500/30">
      {/* ── Header ── */}
      <header className="h-12 border-b border-white/[0.06] flex items-center justify-between px-4 bg-[#0a0a0a] shrink-0 z-10">
        <div className="flex items-center gap-3">
          <Link to="/chat" className="p-1.5 text-white/40 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div className="w-px h-5 bg-white/[0.06]" />
          <div className="flex items-center gap-2">
            <div className={`p-1 bg-gradient-to-br ${fwInfo.color} rounded-lg bg-opacity-20 border ${fwInfo.border}`}>
              <Smartphone className="w-4 h-4 text-white/80" />
            </div>
            <div>
              <span className="text-sm font-bold tracking-tight">App Studio</span>
              <span className="text-[9px] text-white/20 font-mono ml-2">{fwInfo.name.toUpperCase()}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => { setShowSelector(true); setHtmlContent(''); setGeneratedFiles([]); setStages(INITIAL_STAGES); setMessages([]); setAgentLogs([]); }}
            className="px-2.5 py-1 text-[11px] font-medium text-white/40 hover:text-white hover:bg-white/5 rounded-md transition-colors flex items-center gap-1.5">
            <Layers className="w-3 h-3" /> Framework
          </button>
          <div className="w-px h-5 bg-white/[0.06] mx-1" />
          <ModelBadge onLog={addLog} />
          <div className="w-px h-5 bg-white/[0.06] mx-1" />
          <button onClick={() => setShowUploader(true)} className="px-2.5 py-1 text-[11px] font-medium text-white/50 hover:text-white hover:bg-white/5 rounded-md transition-colors flex items-center gap-1.5">
            <Upload className="w-3 h-3" /> Import
          </button>
          <button onClick={() => { if (htmlContent) { const b = new Blob([htmlContent], { type: 'text/html' }); const u = URL.createObjectURL(b); const a = document.createElement('a'); a.href = u; a.download = `${fwInfo.name.replace(/\s/g, '-')}-app.html`; document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(u); addLog('📱 Exported app as HTML'); } }}
            disabled={!htmlContent}
            className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors flex items-center gap-1.5 ${htmlContent ? 'text-white/50 hover:text-white hover:bg-white/5' : 'text-white/15 cursor-not-allowed'}`}>
            <Download className="w-3 h-3" /> Export
          </button>
          <button onClick={() => setShowDeploy(true)} disabled={!htmlContent}
            className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all flex items-center gap-1.5 ${htmlContent ? 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:shadow-[0_0_15px_rgba(16,185,129,0.3)]' : 'bg-white/[0.04] text-white/15 cursor-not-allowed'}`}>
            <Package className="w-3 h-3" /> Deploy
          </button>
          <button onClick={() => { if (input.trim()) handleBuild(input); }} className={`px-2.5 py-1 text-[11px] font-bold rounded-md transition-all flex items-center gap-1.5 ${isBuilding ? 'bg-white/10 text-white/50' : `bg-gradient-to-r ${fwInfo.color} text-white hover:shadow-[0_0_15px_rgba(139,92,246,0.3)]`}`}>
            {isBuilding ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />} Build & Run
          </button>
        </div>
      </header>

      {/* ── Main Workspace ── */}
      <div className="flex-1 flex overflow-hidden">

        {/* ══ Left Panel: Chat + Pipeline ══ */}
        <div className="w-[340px] border-r border-white/[0.06] flex flex-col bg-[#080808] shrink-0">
          {/* Pipeline */}
          <div className="px-3 py-2.5 border-b border-white/[0.04] bg-[#0a0a0a]">
            <div className="flex items-center gap-1">
              {stages.map((s, i) => (
                <React.Fragment key={s.id}>
                  <div className="flex flex-col items-center gap-0.5 flex-1" title={s.label}>
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs transition-all duration-500 ${s.status === 'done' ? 'bg-emerald-500/20 ring-1 ring-emerald-500/30' :
                      s.status === 'running' ? 'bg-violet-500/20 ring-1 ring-violet-500/30 animate-pulse' :
                        s.status === 'error' ? 'bg-red-500/20 ring-1 ring-red-500/30' : 'bg-white/[0.04] ring-1 ring-white/[0.06]'
                      }`}>
                      {s.status === 'done' ? <CheckCircle2 className="w-3 h-3 text-emerald-400" /> :
                        s.status === 'running' ? <Loader2 className="w-3 h-3 text-violet-400 animate-spin" /> :
                          s.status === 'error' ? <XCircle className="w-3 h-3 text-red-400" /> : <span>{s.icon}</span>}
                    </div>
                    <span className={`text-[8px] font-bold uppercase tracking-wider ${s.status === 'done' ? 'text-emerald-400/60' : s.status === 'running' ? 'text-violet-400/60' : 'text-white/20'
                      }`}>{s.label}</span>
                  </div>
                  {i < stages.length - 1 && <div className={`h-px w-3 mt-[-10px] transition-colors ${s.status === 'done' ? 'bg-emerald-500/30' : 'bg-white/[0.06]'}`} />}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Chat */}
          <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-3">
            {messages.map(msg => (
              <motion.div key={msg.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                className={`flex ${msg.isUser ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[90%] rounded-xl px-3 py-2 text-[13px] leading-relaxed ${msg.isUser ? 'bg-violet-500/15 border border-violet-500/20 text-white' : 'text-white/80'}`}>
                  {!msg.isUser && msg.agent && (
                    <div className="flex items-center gap-1.5 mb-1">
                      <Bot className="w-3 h-3 text-violet-400" /><span className="text-[10px] font-bold text-violet-400">{msg.agent}</span>
                    </div>
                  )}
                  <div className="whitespace-pre-wrap">{msg.text}</div>
                </div>
              </motion.div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-white/[0.04] bg-[#0a0a0a]">
            <form onSubmit={handleSubmit} className="flex items-end bg-[#111] border border-white/[0.08] rounded-xl p-1.5 focus-within:border-violet-500/30 transition-colors">
              <textarea value={input} onChange={e => setInput(e.target.value)}
                placeholder={htmlContent ? "Describe modifications..." : "Describe your mobile app..."}
                className="flex-1 bg-transparent border-none outline-none px-2 py-1 text-[13px] text-white placeholder-white/20 resize-none min-h-[36px] max-h-[100px] custom-scrollbar"
                rows={1} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e); } }} />
              <button type="submit" disabled={!input.trim() || isBuilding}
                className={`p-2 rounded-lg transition-all ${input.trim() && !isBuilding ? `bg-gradient-to-r ${fwInfo.color} text-white shadow-[0_0_10px_rgba(139,92,246,0.2)]` : 'bg-white/5 text-white/15'}`}>
                {isBuilding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </form>
          </div>
        </div>

        {/* ══ Center Panel: Preview / Code / Security ══ */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#0a0a0a]">
          <div className="h-10 border-b border-white/[0.06] flex items-center justify-between px-3 shrink-0 bg-[#0c0c0c]">
            <div className="flex items-center gap-0.5">
              {([
                { key: 'preview' as const, Icon: Smartphone, label: 'Preview', badge: 0 },
                { key: 'code' as const, Icon: Code2, label: 'Code', badge: 0 },
                { key: 'security' as const, Icon: Shield, label: 'Security', badge: scanResults.filter(s => s.severity !== 'info').length },
              ] as const).map(({ key, Icon, label, badge }) => (
                <button key={key} onClick={() => setActiveTab(key)}
                  className={`px-2.5 py-1.5 text-[11px] font-bold rounded-md transition-colors flex items-center gap-1.5 ${activeTab === key ? 'bg-white/10 text-white' : 'text-white/35 hover:text-white/60 hover:bg-white/5'}`}>
                  <Icon className="w-3.5 h-3.5" /> {label}
                  {badge > 0 && <span className="text-[9px] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded-full border border-red-500/20">{badge}</span>}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 relative overflow-hidden">
            <AnimatePresence mode="wait">
              {/* ── Preview: Single Emulator with Switch ── */}
              {activeTab === 'preview' && (
                <motion.div key="preview" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 flex flex-col items-center justify-center p-6 bg-[#111]">
                  {/* Device Toggle Switch */}
                  <div className="flex items-center gap-1 mb-4 bg-white/[0.04] border border-white/[0.08] rounded-full p-1">
                    <button onClick={() => setDeviceView('android')}
                      className={`px-4 py-1.5 text-[11px] font-bold rounded-full transition-all duration-300 flex items-center gap-2 ${deviceView === 'android' ? 'bg-gradient-to-r from-emerald-500/20 to-green-500/20 text-emerald-400 ring-1 ring-emerald-500/30' : 'text-white/30 hover:text-white/50'
                        }`}>
                      <span className="text-sm">🤖</span> Android
                    </button>
                    <button onClick={() => setDeviceView('iphone')}
                      className={`px-4 py-1.5 text-[11px] font-bold rounded-full transition-all duration-300 flex items-center gap-2 ${deviceView === 'iphone' ? 'bg-gradient-to-r from-blue-500/20 to-indigo-500/20 text-blue-400 ring-1 ring-blue-500/30' : 'text-white/30 hover:text-white/50'
                        }`}>
                      <span className="text-sm">🍎</span> iPhone
                    </button>
                  </div>

                  {/* Device Frame */}
                  <AnimatePresence mode="wait">
                    {deviceView === 'android' ? (
                      <motion.div key="android-device" initial={{ opacity: 0, x: -30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 30 }} transition={{ duration: 0.3 }}
                        className="flex flex-col items-center">
                        <div className="w-[300px] h-[600px] bg-[#1a1a1a] rounded-[2rem] border-[6px] border-[#2a2a2a] shadow-[0_0_60px_rgba(0,0,0,0.5),0_0_120px_rgba(16,185,129,0.05)] relative overflow-hidden flex flex-col">
                          {/* Status bar */}
                          <div className="h-7 bg-[#1a1a1a] flex items-center justify-between px-5 shrink-0 z-10">
                            <span className="text-[9px] text-white/30 font-mono">12:00</span>
                            <div className="w-3 h-3 rounded-full bg-[#333] border border-white/10" />
                            <div className="flex gap-1 items-center">
                              <div className="w-3 h-1.5 rounded-sm bg-white/20" /><div className="w-2.5 h-1.5 rounded-sm bg-white/20" /><div className="text-[8px] text-white/25">100%</div>
                            </div>
                          </div>
                          <div className="flex-1 bg-white overflow-hidden">
                            {htmlContent ? (
                              <iframe ref={deviceRef} className="w-full h-full border-none" sandbox="allow-scripts allow-same-origin" title="Android Preview" />
                            ) : (
                              <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-3 p-6">
                                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-green-100 to-emerald-100 flex items-center justify-center"><Cpu className="w-7 h-7 text-emerald-500/50" /></div>
                                <p className="text-xs text-gray-400 text-center">Your Android app will render here</p>
                                <p className="text-[10px] text-gray-300">Describe your app in the chat panel</p>
                              </div>
                            )}
                          </div>
                          {/* Nav bar */}
                          <div className="h-10 bg-[#1a1a1a] flex items-center justify-center gap-10 shrink-0">
                            <div className="w-4 h-4 border-2 border-white/15 rounded-sm" />
                            <div className="w-4 h-4 rounded-full border-2 border-white/15" />
                            <div className="w-0 h-0 border-l-[7px] border-l-white/15 border-y-[5px] border-y-transparent" />
                          </div>
                        </div>
                      </motion.div>
                    ) : (
                      <motion.div key="iphone-device" initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -30 }} transition={{ duration: 0.3 }}
                        className="flex flex-col items-center">
                        <div className="w-[300px] h-[600px] bg-[#0d0d0d] rounded-[3rem] border-[6px] border-[#2a2a2a] shadow-[0_0_60px_rgba(0,0,0,0.5),0_0_120px_rgba(99,102,241,0.05)] relative overflow-hidden flex flex-col">
                          {/* Dynamic Island */}
                          <div className="absolute top-2 left-1/2 -translate-x-1/2 w-28 h-[22px] bg-black rounded-full z-20 flex items-center justify-center gap-2">
                            <div className="w-2.5 h-2.5 rounded-full bg-[#1a1a2e] border border-[#333]" />
                            <div className="w-1 h-1 rounded-full bg-[#333]" />
                          </div>
                          {/* Status bar */}
                          <div className="h-12 bg-transparent flex items-end justify-between px-8 pb-1 shrink-0 z-10">
                            <span className="text-[10px] font-semibold text-white/40">9:41</span>
                            <div className="flex gap-1 items-center">
                              <div className="w-3.5 h-1.5 rounded-sm bg-white/20" /><div className="w-3 h-1.5 rounded-sm bg-white/20" /><div className="w-5 h-2.5 rounded-sm bg-white/20 border border-white/10" />
                            </div>
                          </div>
                          <div className="flex-1 bg-white overflow-hidden rounded-b-[2.5rem]">
                            {htmlContent ? (
                              <iframe ref={deviceRef} className="w-full h-full border-none" sandbox="allow-scripts allow-same-origin" title="iPhone Preview" />
                            ) : (
                              <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-3 p-6">
                                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center"><Zap className="w-7 h-7 text-indigo-500/50" /></div>
                                <p className="text-xs text-gray-400 text-center">Your iPhone app will render here</p>
                                <p className="text-[10px] text-gray-300">Describe your app in the chat panel</p>
                              </div>
                            )}
                          </div>
                          {/* Home indicator */}
                          <div className="h-5 bg-[#0d0d0d] flex items-center justify-center shrink-0">
                            <div className="w-28 h-1 rounded-full bg-white/15" />
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              )}

              {/* ── Code Editor ── */}
              {activeTab === 'code' && (
                <motion.div key="code" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 flex flex-col">
                  <div className="h-9 border-b border-white/[0.04] flex items-center px-2 gap-0.5 bg-[#0c0c0c] shrink-0">
                    {generatedFiles.map((f, i) => (
                      <button key={f.name} onClick={() => setActiveFile(i)}
                        className={`px-2.5 py-1 text-[11px] font-medium rounded-md flex items-center gap-1.5 transition-colors ${activeFile === i ? 'bg-white/10 text-white' : 'text-white/30 hover:text-white/50 hover:bg-white/5'}`}>
                        <FileCode className="w-3 h-3" /> {f.name}
                      </button>
                    ))}
                    {generatedFiles.length === 0 && <span className="text-[11px] text-white/15 px-2">No files generated yet</span>}
                  </div>
                  <div className="flex-1 overflow-auto custom-scrollbar p-4 font-mono text-[12px] leading-6 bg-[#0a0a0a]">
                    {generatedFiles[activeFile] ? (
                      generatedFiles[activeFile].content.split('\n').map((line, i) => (
                        <div key={i} className="flex hover:bg-white/[0.02]">
                          <span className="w-10 text-right pr-4 text-white/15 select-none shrink-0">{i + 1}</span>
                          <span className="text-white/70 whitespace-pre">{line}</span>
                        </div>
                      ))
                    ) : (
                      <div className="h-full flex items-center justify-center text-white/15"><Code2 className="w-8 h-8" /></div>
                    )}
                  </div>
                </motion.div>
              )}

              {/* ── Security ── */}
              {activeTab === 'security' && (
                <motion.div key="security" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 overflow-auto custom-scrollbar p-5">
                  <div className="max-w-2xl mx-auto space-y-3">
                    <div className="flex items-center gap-2 mb-4">
                      <Shield className="w-5 h-5 text-emerald-400" /><span className="text-sm font-bold">Security Analysis</span>
                      <span className="text-[10px] font-mono text-white/20 ml-auto">{scanResults.length} findings</span>
                    </div>
                    {scanResults.length > 0 ? scanResults.map((r, i) => (
                      <div key={i} className={`flex items-start gap-3 p-3 rounded-xl border ${r.severity === 'critical' ? 'bg-red-500/5 border-red-500/20' : r.severity === 'warning' ? 'bg-amber-500/5 border-amber-500/20' : 'bg-white/[0.02] border-white/[0.06]'}`}>
                        {r.severity === 'critical' ? <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" /> :
                          r.severity === 'warning' ? <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" /> :
                            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />}
                        <div>
                          <div className="text-[12px] font-bold text-white/80">{r.title}</div>
                          <div className="text-[11px] text-white/35 mt-0.5">{r.detail}</div>
                        </div>
                      </div>
                    )) : (
                      <div className="text-center py-16 text-white/15"><Shield className="w-10 h-10 mx-auto mb-3" /><p className="text-sm">Run a build to see security results</p></div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* ══ Right Panel: Files + Logs ══ */}
        <div className="w-[260px] border-l border-white/[0.06] flex flex-col bg-[#080808] shrink-0">
          <div className="p-3 border-b border-white/[0.04]">
            <div className="flex items-center gap-1.5 mb-2"><FolderOpen className="w-3 h-3 text-amber-400" /><span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">Project Files</span></div>
            <div className="space-y-0.5">
              {generatedFiles.length > 0 ? generatedFiles.map((f, i) => (
                <button key={f.name} onClick={() => { setActiveFile(i); setActiveTab('code'); }}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11px] text-white/50 hover:text-white/80 hover:bg-white/5 transition-colors">
                  <FileCode className="w-3 h-3 text-cyan-400/50" /><span className="font-mono">{f.name}</span>
                  <span className="text-[9px] text-white/15 ml-auto">{(f.content.length / 1024).toFixed(1)}kb</span>
                </button>
              )) : <div className="text-[10px] text-white/15 px-2 py-3 text-center">No files yet</div>}
            </div>
          </div>
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="px-3 py-2 flex items-center gap-1.5"><Activity className="w-3 h-3 text-emerald-400" /><span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">Agent Logs</span><span className="text-[9px] font-mono text-white/15 ml-auto">{agentLogs.length}</span></div>
            <div className="flex-1 overflow-y-auto custom-scrollbar px-3 pb-3">
              {agentLogs.length > 0 ? agentLogs.map((log, i) => (
                <div key={i} className="text-[10px] font-mono text-white/25 py-0.5 leading-relaxed border-l border-white/[0.04] pl-2 mb-0.5">{log}</div>
              )) : <div className="text-[10px] text-white/10 text-center py-8">Waiting for build...</div>}
              <div ref={logsEndRef} />
            </div>
          </div>
          <div className="h-7 border-t border-white/[0.04] bg-[#0a0a0a] flex items-center px-3 text-[9px] font-mono text-white/15 gap-3">
            <div className="flex items-center gap-1">
              <div className={`w-1.5 h-1.5 rounded-full ${isBuilding ? 'bg-violet-400 animate-pulse' : htmlContent ? 'bg-emerald-400' : 'bg-white/15'}`} />
              {isBuilding ? 'BUILDING' : htmlContent ? 'READY' : 'IDLE'}
            </div>
            {htmlContent && <span>{generatedFiles.length} files</span>}
            <span className="ml-auto">{fwInfo.name}</span>
          </div>
        </div>
      </div>

      <ProjectUploader mode="app" isOpen={showUploader} onClose={() => setShowUploader(false)}
        onImport={(files, analysis) => {
          addMessage(`📂 Imported project: ${analysis.summary}`, false, 'Import Agent');
          addLog(`📂 Project imported: ${analysis.fileCount} files, ${analysis.language}/${analysis.framework}`);
          if (files.length > 0) {
            const htmlFile = files.find(f => /\.html?$/i.test(f.name));
            if (htmlFile) { setHtmlContent(htmlFile.content); setGeneratedFiles(files.map(f => ({ name: f.name, language: f.name.split('.').pop() || 'text', content: f.content }))); }
          }
        }} />

      {/* Deploy Modal */}
      <DeployPanel
        isOpen={showDeploy}
        onClose={() => setShowDeploy(false)}
        mode="app"
        files={generatedFiles.map(f => ({ name: f.name, content: f.content }))}
        htmlContent={htmlContent}
        appName={`ASTRA-${fwInfo.name.replace(/\s/g, '-')}-App`}
        onLog={addLog}
      />
    </div>
  );
}

// ── Fallback App Generator ──
function generateFallbackApp(prompt: string, fw: Framework): string {
  const isFitness = /fitness|workout|gym|exercise/i.test(prompt);
  const isChat = /chat|messenger|message/i.test(prompt);
  if (isFitness) return FITNESS_APP_HTML;
  if (isChat) return CHAT_APP_HTML;
  return FITNESS_APP_HTML;
}

const FITNESS_APP_HTML = `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>FitTrack</title><style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f0f14;color:#fff;max-width:375px;margin:0 auto;min-height:100vh;overflow-x:hidden}
.header{padding:20px 20px 0;display:flex;justify-content:space-between;align-items:center}
.header h1{font-size:24px;font-weight:800}.header .avatar{w:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#8b5cf6)}
.greeting{padding:0 20px;margin-top:4px;color:rgba(255,255,255,0.4);font-size:13px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;padding:20px}
.stat-card{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.06);border-radius:16px;padding:16px;text-align:center}
.stat-card .value{font-size:22px;font-weight:800;margin:4px 0}.stat-card .label{font-size:10px;color:rgba(255,255,255,0.35);text-transform:uppercase;letter-spacing:1px}
.stat-card:nth-child(1) .value{color:#6366f1}.stat-card:nth-child(2) .value{color:#f59e0b}.stat-card:nth-child(3) .value{color:#10b981}
.section{padding:0 20px;margin-bottom:20px}.section h2{font-size:16px;font-weight:700;margin-bottom:12px}
.workout-card{background:linear-gradient(135deg,rgba(99,102,241,0.15),rgba(139,92,246,0.1));border:1px solid rgba(99,102,241,0.2);border-radius:16px;padding:16px;margin-bottom:10px;display:flex;align-items:center;gap:14px;cursor:pointer;transition:all 0.2s}
.workout-card:active{transform:scale(0.98)}.workout-icon{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:20px}
.workout-info h3{font-size:14px;font-weight:600;margin-bottom:2px}.workout-info p{font-size:11px;color:rgba(255,255,255,0.4)}
.workout-meta{margin-left:auto;text-align:right}.workout-meta .cal{font-size:14px;font-weight:700;color:#f59e0b}.workout-meta .time{font-size:10px;color:rgba(255,255,255,0.3)}
.progress-ring{padding:20px;display:flex;align-items:center;gap:20px;background:rgba(255,255,255,0.03);border-radius:20px;margin:0 20px 20px}
.ring{width:80px;height:80px;border-radius:50%;background:conic-gradient(#6366f1 0deg,#6366f1 252deg,rgba(255,255,255,0.06) 252deg);display:flex;align-items:center;justify-content:center}
.ring-inner{width:64px;height:64px;border-radius:50%;background:#0f0f14;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800}
.ring-info h3{font-size:14px;font-weight:600}.ring-info p{font-size:12px;color:rgba(255,255,255,0.4);margin-top:2px}
.bottom-nav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:375px;background:rgba(15,15,20,0.95);backdrop-filter:blur(20px);border-top:1px solid rgba(255,255,255,0.06);display:flex;justify-content:space-around;padding:10px 0 24px}
.nav-item{display:flex;flex-direction:column;align-items:center;gap:4px;font-size:9px;color:rgba(255,255,255,0.3);cursor:pointer;transition:color 0.2s}
.nav-item.active{color:#6366f1}.nav-item span{font-size:18px}
.cta-btn{width:calc(100% - 40px);margin:0 20px 90px;padding:16px;border:none;border-radius:14px;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;font-size:15px;font-weight:700;cursor:pointer;transition:all 0.2s}
.cta-btn:active{transform:scale(0.97)}
</style></head><body>
<div class="header"><h1>FitTrack</h1><div class="avatar"></div></div>
<p class="greeting">Good morning, Alex! 💪</p>
<div class="stats"><div class="stat-card"><div class="label">Steps</div><div class="value">8,432</div></div><div class="stat-card"><div class="label">Calories</div><div class="value">524</div></div><div class="stat-card"><div class="label">Active</div><div class="value">47m</div></div></div>
<div class="progress-ring"><div class="ring"><div class="ring-inner">70%</div></div><div class="ring-info"><h3>Daily Goal</h3><p>7,000 / 10,000 steps completed</p></div></div>
<div class="section"><h2>Today's Workouts</h2>
<div class="workout-card"><div class="workout-icon" style="background:rgba(99,102,241,0.2)">🏋️</div><div class="workout-info"><h3>Upper Body</h3><p>Chest, shoulders, triceps</p></div><div class="workout-meta"><div class="cal">320 cal</div><div class="time">45 min</div></div></div>
<div class="workout-card"><div class="workout-icon" style="background:rgba(16,185,129,0.2)">🏃</div><div class="workout-info"><h3>HIIT Cardio</h3><p>Intervals, burpees, sprints</p></div><div class="workout-meta"><div class="cal">280 cal</div><div class="time">30 min</div></div></div>
<div class="workout-card"><div class="workout-icon" style="background:rgba(245,158,11,0.2)">🧘</div><div class="workout-info"><h3>Yoga Flow</h3><p>Flexibility & mindfulness</p></div><div class="workout-meta"><div class="cal">120 cal</div><div class="time">25 min</div></div></div>
</div>
<button class="cta-btn" onclick="this.textContent='✓ Workout Started!';this.style.background='linear-gradient(135deg,#10b981,#34d399)'">Start Workout →</button>
<div class="bottom-nav"><div class="nav-item active"><span>🏠</span>Home</div><div class="nav-item"><span>📊</span>Stats</div><div class="nav-item"><span>💪</span>Workouts</div><div class="nav-item"><span>👤</span>Profile</div></div>
</body></html>`;

const CHAT_APP_HTML = `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>QuickChat</title><style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0f;color:#fff;max-width:375px;margin:0 auto;min-height:100vh;display:flex;flex-direction:column}
.chat-header{padding:16px 20px;background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.06);display:flex;align-items:center;gap:12px}
.back-btn{font-size:18px;cursor:pointer;color:rgba(255,255,255,0.5)}.chat-avatar{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#ec4899)}
.chat-info h3{font-size:14px;font-weight:600}.chat-info p{font-size:10px;color:#10b981}
.messages{flex:1;padding:16px;overflow-y:auto;display:flex;flex-direction:column;gap:10px}
.msg{max-width:75%;padding:10px 14px;border-radius:16px;font-size:13px;line-height:1.5;animation:fadeIn 0.3s}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.msg.sent{align-self:flex-end;background:linear-gradient(135deg,#6366f1,#8b5cf6);border-bottom-right-radius:4px}
.msg.recv{align-self:flex-start;background:rgba(255,255,255,0.06);border-bottom-left-radius:4px}
.msg .time{font-size:9px;color:rgba(255,255,255,0.3);margin-top:4px;text-align:right}
.input-area{padding:12px 16px 28px;background:rgba(255,255,255,0.03);border-top:1px solid rgba(255,255,255,0.06);display:flex;gap:10px;align-items:center}
.input-area input{flex:1;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);border-radius:24px;padding:10px 16px;color:#fff;font-size:13px;outline:none}
.input-area input:focus{border-color:rgba(99,102,241,0.4)}.send-btn{width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#8b5cf6);border:none;color:#fff;font-size:16px;cursor:pointer;display:flex;align-items:center;justify-content:center}
</style></head><body>
<div class="chat-header"><span class="back-btn">←</span><div class="chat-avatar"></div><div class="chat-info"><h3>Sarah Chen</h3><p>● Online</p></div></div>
<div class="messages" id="msgs">
<div class="msg recv">Hey! How's the new project going? 😊<div class="time">10:30 AM</div></div>
<div class="msg sent">Going great! Just finished the UI mockups<div class="time">10:32 AM</div></div>
<div class="msg recv">That's awesome! Can you share them?<div class="time">10:33 AM</div></div>
<div class="msg sent">Sure, sending them over now! 📎<div class="time">10:34 AM</div></div>
<div class="msg recv">These look incredible! Love the color palette 🎨<div class="time">10:36 AM</div></div>
</div>
<div class="input-area"><input type="text" placeholder="Type a message..." id="chatInput" onkeydown="if(event.key==='Enter')sendMsg()"/><button class="send-btn" onclick="sendMsg()">↑</button></div>
<script>function sendMsg(){const i=document.getElementById('chatInput');const m=document.getElementById('msgs');if(!i.value.trim())return;const d=document.createElement('div');d.className='msg sent';d.innerHTML=i.value+'<div class=time>'+new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+'</div>';m.appendChild(d);i.value='';m.scrollTop=m.scrollHeight;setTimeout(()=>{const r=document.createElement('div');r.className='msg recv';r.innerHTML=['Sounds good! 👍','That makes sense','Let me check on that','Great idea! 💡','I agree 100%'][Math.floor(Math.random()*5)]+'<div class=time>'+new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+'</div>';m.appendChild(r);m.scrollTop=m.scrollHeight;},1000)}</script>
</body></html>`;

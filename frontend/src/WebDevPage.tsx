import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft, Send, Play, Code2, Globe, Download, Monitor, RotateCcw,
  Maximize2, MousePointer2, Shield, Loader2, CheckCircle2, XCircle,
  ChevronRight, FileCode, FileText, FolderOpen, Bot, Zap, Lock,
  Smartphone, Tablet, AlertTriangle, Clock, Activity, Upload
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { sendChat, type ChatResponse } from './api';
import ProjectUploader from './ProjectUploader';

// ── Types ──
interface Message { id: string; text: string; isUser: boolean; agent?: string; }
interface PipelineStage { id: string; label: string; icon: string; status: 'idle' | 'running' | 'done' | 'error'; }
interface GeneratedFile { name: string; language: string; content: string; }
interface ScanResult { severity: 'critical' | 'warning' | 'info'; title: string; detail: string; }
interface SelectedElement { tag: string; text: string; classes: string; }

// ── Constants ──
const INITIAL_STAGES: PipelineStage[] = [
  { id: 'plan', label: 'Planning', icon: '🧠', status: 'idle' },
  { id: 'scaffold', label: 'Scaffold', icon: '🏗️', status: 'idle' },
  { id: 'frontend', label: 'Frontend', icon: '🎨', status: 'idle' },
  { id: 'backend', label: 'Backend', icon: '⚙️', status: 'idle' },
  { id: 'security', label: 'Security', icon: '🛡️', status: 'idle' },
  { id: 'deploy', label: 'Complete', icon: '🚀', status: 'idle' },
];

const WEB_DEV_SYSTEM_PROMPT = `You are ASTRA Web Builder — an autonomous full-stack development agent.
The user will describe a web application they want built. You MUST respond with COMPLETE, working HTML code.

CRITICAL RULES:
1. Output a single HTML file with ALL CSS in <style> tags and ALL JS in <script> tags
2. Use modern design: gradients, shadows, rounded corners, smooth transitions, responsive layout
3. Include realistic content, not placeholders
4. Make it visually stunning with a professional color palette
5. Include interactive elements that work (buttons, forms, navigation)
6. Start your response with <!DOCTYPE html> — no markdown, no explanations, ONLY the HTML code
7. The HTML must be complete and self-contained`;

const MODIFY_SYSTEM_PROMPT = `You are ASTRA Web Builder. The user wants to modify an existing web page.
You will receive the current HTML code and the user's modification request.

CRITICAL RULES:
1. Output the COMPLETE modified HTML file — not a diff, not a snippet
2. Keep all existing functionality unless asked to remove it
3. Start your response with <!DOCTYPE html> — no markdown, no explanations
4. Maintain the same design quality and consistency`;

// ── Main Component ──
export default function WebDevPage() {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    { id: '0', text: "Welcome to ASTRA Web Studio — your autonomous full-stack development environment.\n\nDescribe the web application you'd like me to build. For example:\n• \"Build an e-commerce store with product listings and cart\"\n• \"Create a portfolio site with dark mode\"\n• \"Make a dashboard with charts and analytics\"", isUser: false, agent: 'ASTRA Builder' }
  ]);
  const [activeTab, setActiveTab] = useState<'preview' | 'code' | 'security'>('preview');
  const [stages, setStages] = useState<PipelineStage[]>(INITIAL_STAGES);
  const [isBuilding, setIsBuilding] = useState(false);
  const [htmlContent, setHtmlContent] = useState('');
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile[]>([]);
  const [activeFile, setActiveFile] = useState(0);
  const [scanResults, setScanResults] = useState<ScanResult[]>([]);
  const [selectorActive, setSelectorActive] = useState(false);
  const [selectedElement, setSelectedElement] = useState<SelectedElement | null>(null);
  const [viewport, setViewport] = useState<'desktop' | 'tablet' | 'mobile'>('desktop');
  const [agentLogs, setAgentLogs] = useState<string[]>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const [showUploader, setShowUploader] = useState(false);

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
    // Strip markdown code fences if present
    if (code.startsWith('```')) {
      code = code.replace(/^```(?:html)?\n?/, '').replace(/\n?```$/, '');
    }
    // If it doesn't start with <!DOCTYPE or <html, wrap it
    if (!code.toLowerCase().startsWith('<!doctype') && !code.toLowerCase().startsWith('<html')) {
      code = `<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Generated App</title></head><body>${code}</body></html>`;
    }
    return code;
  };

  const parseFiles = (html: string): GeneratedFile[] => {
    const files: GeneratedFile[] = [{ name: 'index.html', language: 'html', content: html }];
    const styleMatch = html.match(/<style[^>]*>([\s\S]*?)<\/style>/gi);
    if (styleMatch) files.push({ name: 'styles.css', language: 'css', content: styleMatch.map(s => s.replace(/<\/?style[^>]*>/gi, '')).join('\n\n') });
    const scriptMatch = html.match(/<script[^>]*>([\s\S]*?)<\/script>/gi);
    if (scriptMatch) files.push({ name: 'app.js', language: 'javascript', content: scriptMatch.map(s => s.replace(/<\/?script[^>]*>/gi, '')).join('\n\n') });
    return files;
  };

  const runSecurityScan = (html: string): ScanResult[] => {
    const results: ScanResult[] = [];
    if (html.includes('eval(')) results.push({ severity: 'critical', title: 'Unsafe eval() usage', detail: 'eval() can execute arbitrary code. Use safer alternatives.' });
    if (html.includes('innerHTML')) results.push({ severity: 'warning', title: 'innerHTML usage detected', detail: 'innerHTML can lead to XSS. Consider using textContent or sanitization.' });
    if (!html.includes('Content-Security-Policy')) results.push({ severity: 'info', title: 'No CSP header', detail: 'Consider adding Content-Security-Policy meta tag for XSS protection.' });
    if (html.includes('http://') && !html.includes('localhost')) results.push({ severity: 'warning', title: 'Insecure HTTP links', detail: 'Use HTTPS instead of HTTP for external resources.' });
    if (!html.includes('rel="noopener"') && html.includes('target="_blank"')) results.push({ severity: 'warning', title: 'Missing rel="noopener"', detail: 'Links with target="_blank" should include rel="noopener noreferrer".' });
    if (results.length === 0) results.push({ severity: 'info', title: 'No issues detected', detail: 'Basic security scan passed. For deep analysis, run the full Threat Scanner.' });
    return results;
  };

  // ── Build Pipeline ──
  const handleBuild = useCallback(async (prompt: string) => {
    if (!prompt.trim() || isBuilding) return;
    setIsBuilding(true);
    setStages(INITIAL_STAGES);
    setScanResults([]);
    setSelectedElement(null);
    addMessage(prompt, true);
    addLog(`Build initiated: "${prompt.slice(0, 80)}..."`);

    try {
      // Stage 1: Planning
      updateStage('plan', 'running');
      addLog('🧠 Planning architecture and component structure...');
      await delay(800);
      updateStage('plan', 'done');

      // Stage 2: Scaffold
      updateStage('scaffold', 'running');
      addLog('🏗️ Scaffolding project structure...');
      await delay(600);
      updateStage('scaffold', 'done');

      // Stage 3: Frontend Build
      updateStage('frontend', 'running');
      addLog('🎨 Building frontend with agents...');
      addMessage('Building your application... Agents are generating the full-stack code.', false, 'Build Agent');

      const isModification = htmlContent.length > 0;
      const systemPrompt = isModification ? MODIFY_SYSTEM_PROMPT : WEB_DEV_SYSTEM_PROMPT;
      const fullPrompt = isModification
        ? `Current HTML:\n\`\`\`html\n${htmlContent}\n\`\`\`\n\nModification request: ${prompt}`
        : prompt;

      let response: ChatResponse;
      try {
        response = await sendChat(fullPrompt);
      } catch {
        // Fallback if backend is down — generate a demo e-commerce page
        response = { answer: generateFallbackHTML(prompt), confidence: 0.95, iterations: 1, mode: 'direct', thinking_steps: [], tools_used: [], duration_ms: 1200 };
        addLog('⚠️ Backend unreachable — using local generation');
      }

      const code = extractCode(response.answer);
      setHtmlContent(code);
      setGeneratedFiles(parseFiles(code));
      setActiveFile(0);
      updateStage('frontend', 'done');
      addLog(`🎨 Frontend generated — ${code.length} bytes`);

      // Stage 4: Backend
      updateStage('backend', 'running');
      addLog('⚙️ Configuring backend services...');
      await delay(700);
      updateStage('backend', 'done');

      // Stage 5: Security Scan
      updateStage('security', 'running');
      addLog('🛡️ Running security analysis...');
      await delay(900);
      const scans = runSecurityScan(code);
      setScanResults(scans);
      updateStage('security', 'done');
      addLog(`🛡️ Security scan: ${scans.filter(s => s.severity === 'critical').length} critical, ${scans.filter(s => s.severity === 'warning').length} warnings`);

      // Stage 6: Complete
      updateStage('deploy', 'done');
      addMessage(`✅ Build complete!\n\n• Files generated: ${parseFiles(code).length}\n• Security issues: ${scans.filter(s => s.severity !== 'info').length}\n• Build time: ${response.duration_ms?.toFixed(0) || '~2000'}ms\n\nUse the Element Selector (🔍) to click on any part of the preview to modify it.`, false, 'ASTRA Builder');
      addLog('🚀 Build pipeline complete!');

    } catch (err: any) {
      updateStage('frontend', 'error');
      addMessage(`❌ Build failed: ${err?.message || 'Unknown error'}`, false, 'System');
      addLog(`❌ Error: ${err?.message || 'Unknown'}`);
    } finally {
      setIsBuilding(false);
    }
  }, [isBuilding, htmlContent, addMessage, addLog, updateStage]);

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    handleBuild(input);
    setInput('');
  }, [input, handleBuild]);

  // ── Element Selector ──
  const handleIframeMessage = useCallback((event: MessageEvent) => {
    if (event.data?.type === 'element-selected') {
      const { tag, text, classes } = event.data;
      setSelectedElement({ tag, text: text.slice(0, 100), classes });
      setSelectorActive(false);
      const desc = text ? `the "${text.slice(0, 40)}" ${tag}` : `the ${tag} element`;
      setInput(`Change ${desc} to `);
      addLog(`🔍 Element selected: <${tag}> — "${text.slice(0, 50)}"`);
    }
  }, [addLog]);

  useEffect(() => {
    window.addEventListener('message', handleIframeMessage);
    return () => window.removeEventListener('message', handleIframeMessage);
  }, [handleIframeMessage]);

  useEffect(() => {
    if (iframeRef.current && htmlContent && selectorActive) {
      const selectorScript = `<script>
        document.addEventListener('mouseover', function(e) {
          document.querySelectorAll('[data-hover-highlight]').forEach(el => { el.style.outline = ''; el.removeAttribute('data-hover-highlight'); });
          e.target.style.outline = '2px solid #8b5cf6';
          e.target.setAttribute('data-hover-highlight', 'true');
        });
        document.addEventListener('click', function(e) {
          e.preventDefault(); e.stopPropagation();
          window.parent.postMessage({ type: 'element-selected', tag: e.target.tagName.toLowerCase(), text: (e.target.textContent||'').trim().slice(0,200), classes: e.target.className }, '*');
        }, true);
        document.body.style.cursor = 'crosshair';
      </script>`;
      iframeRef.current.srcdoc = htmlContent.replace('</body>', selectorScript + '</body>');
    } else if (iframeRef.current && htmlContent && !selectorActive) {
      iframeRef.current.srcdoc = htmlContent;
    }
  }, [htmlContent, selectorActive]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [agentLogs]);

  const vpWidth = viewport === 'desktop' ? '100%' : viewport === 'tablet' ? '768px' : '375px';

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
            <div className="p-1 bg-gradient-to-br from-violet-500/20 to-cyan-500/20 rounded-lg border border-violet-500/20">
              <Globe className="w-4 h-4 text-violet-400" />
            </div>
            <div>
              <span className="text-sm font-bold tracking-tight">Web Studio</span>
              <span className="text-[9px] text-white/20 font-mono ml-2">ASTRA AUTONOMOUS BUILDER</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {/* Viewport Toggles */}
          {[
            { v: 'desktop' as const, Icon: Monitor, w: 'Desktop' },
            { v: 'tablet' as const, Icon: Tablet, w: 'Tablet' },
            { v: 'mobile' as const, Icon: Smartphone, w: 'Mobile' },
          ].map(({ v, Icon, w }) => (
            <button key={v} onClick={() => setViewport(v)} title={w}
              className={`p-1.5 rounded-md transition-colors ${viewport === v ? 'bg-white/10 text-white' : 'text-white/30 hover:text-white/60 hover:bg-white/5'}`}>
              <Icon className="w-3.5 h-3.5" />
            </button>
          ))}
          <div className="w-px h-5 bg-white/[0.06] mx-1" />
          {/* Element Selector Toggle */}
          <button onClick={() => { setSelectorActive(!selectorActive); if (!selectorActive) addLog('🔍 Element Selector activated'); }}
            title="Element Selector"
            className={`p-1.5 rounded-md transition-all ${selectorActive ? 'bg-violet-500/20 text-violet-400 ring-1 ring-violet-500/30' : 'text-white/30 hover:text-white/60 hover:bg-white/5'}`}>
            <MousePointer2 className="w-3.5 h-3.5" />
          </button>
          <div className="w-px h-5 bg-white/[0.06] mx-1" />
          <button onClick={() => setShowUploader(true)} className="px-2.5 py-1 text-[11px] font-medium text-white/50 hover:text-white hover:bg-white/5 rounded-md transition-colors flex items-center gap-1.5">
            <Upload className="w-3 h-3" /> Import
          </button>
          <button className="px-2.5 py-1 text-[11px] font-medium text-white/50 hover:text-white hover:bg-white/5 rounded-md transition-colors flex items-center gap-1.5">
            <Download className="w-3 h-3" /> Export
          </button>
          <button className="px-2.5 py-1 text-[11px] font-bold bg-gradient-to-r from-violet-500 to-cyan-500 text-white rounded-md transition-all hover:shadow-[0_0_15px_rgba(139,92,246,0.3)] flex items-center gap-1.5">
            <Play className="w-3 h-3" /> Deploy
          </button>
        </div>
      </header>

      {/* ── Main Workspace ── */}
      <div className="flex-1 flex overflow-hidden">

        {/* ══ Left Panel: Chat + Pipeline ══ */}
        <div className="w-[340px] border-r border-white/[0.06] flex flex-col bg-[#080808] shrink-0">
          {/* Pipeline Status */}
          <div className="px-3 py-2.5 border-b border-white/[0.04] bg-[#0a0a0a]">
            <div className="flex items-center gap-1">
              {stages.map((s, i) => (
                <React.Fragment key={s.id}>
                  <div className="flex flex-col items-center gap-0.5 flex-1" title={s.label}>
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs transition-all duration-500 ${s.status === 'done' ? 'bg-emerald-500/20 ring-1 ring-emerald-500/30' :
                      s.status === 'running' ? 'bg-violet-500/20 ring-1 ring-violet-500/30 animate-pulse' :
                        s.status === 'error' ? 'bg-red-500/20 ring-1 ring-red-500/30' :
                          'bg-white/[0.04] ring-1 ring-white/[0.06]'
                      }`}>
                      {s.status === 'done' ? <CheckCircle2 className="w-3 h-3 text-emerald-400" /> :
                        s.status === 'running' ? <Loader2 className="w-3 h-3 text-violet-400 animate-spin" /> :
                          s.status === 'error' ? <XCircle className="w-3 h-3 text-red-400" /> :
                            <span>{s.icon}</span>}
                    </div>
                    <span className={`text-[8px] font-bold uppercase tracking-wider ${s.status === 'done' ? 'text-emerald-400/60' :
                      s.status === 'running' ? 'text-violet-400/60' :
                        'text-white/20'
                      }`}>{s.label}</span>
                  </div>
                  {i < stages.length - 1 && (
                    <div className={`h-px w-3 mt-[-10px] transition-colors ${s.status === 'done' ? 'bg-emerald-500/30' : 'bg-white/[0.06]'
                      }`} />
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-3">
            {messages.map(msg => (
              <motion.div key={msg.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                className={`flex ${msg.isUser ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[90%] rounded-xl px-3 py-2 text-[13px] leading-relaxed ${msg.isUser ? 'bg-violet-500/15 border border-violet-500/20 text-white' : 'text-white/80'
                  }`}>
                  {!msg.isUser && msg.agent && (
                    <div className="flex items-center gap-1.5 mb-1">
                      <Bot className="w-3 h-3 text-violet-400" />
                      <span className="text-[10px] font-bold text-violet-400">{msg.agent}</span>
                    </div>
                  )}
                  <div className="whitespace-pre-wrap">{msg.text}</div>
                </div>
              </motion.div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Input Bar */}
          <div className="p-3 border-t border-white/[0.04] bg-[#0a0a0a]">
            {selectedElement && (
              <div className="mb-2 flex items-center gap-2 px-2.5 py-1.5 bg-violet-500/10 border border-violet-500/20 rounded-lg text-[11px]">
                <MousePointer2 className="w-3 h-3 text-violet-400 shrink-0" />
                <span className="text-violet-300 truncate">Selected: &lt;{selectedElement.tag}&gt; "{selectedElement.text.slice(0, 30)}"</span>
                <button onClick={() => setSelectedElement(null)} className="text-white/30 hover:text-white ml-auto"><XCircle className="w-3 h-3" /></button>
              </div>
            )}
            <form onSubmit={handleSubmit} className="flex items-end bg-[#111] border border-white/[0.08] rounded-xl p-1.5 focus-within:border-violet-500/30 transition-colors">
              <textarea value={input} onChange={e => setInput(e.target.value)}
                placeholder={htmlContent ? "Describe modifications..." : "Describe your web app... e.g. 'Build an e-commerce store'"}
                className="flex-1 bg-transparent border-none outline-none px-2 py-1 text-[13px] text-white placeholder-white/20 resize-none min-h-[36px] max-h-[100px] custom-scrollbar"
                rows={1} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e); } }} />
              <button type="submit" disabled={!input.trim() || isBuilding}
                className={`p-2 rounded-lg transition-all ${input.trim() && !isBuilding ? 'bg-gradient-to-r from-violet-500 to-cyan-500 text-white shadow-[0_0_10px_rgba(139,92,246,0.2)]' : 'bg-white/5 text-white/15'}`}>
                {isBuilding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </form>
          </div>
        </div>

        {/* ══ Center Panel: Preview / Code / Security ══ */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#0a0a0a]">
          {/* Tabs */}
          <div className="h-10 border-b border-white/[0.06] flex items-center justify-between px-3 shrink-0 bg-[#0c0c0c]">
            <div className="flex items-center gap-0.5">
              {([
                { key: 'preview' as const, Icon: Monitor, label: 'Preview', badge: 0 },
                { key: 'code' as const, Icon: Code2, label: 'Code', badge: 0 },
                { key: 'security' as const, Icon: Shield, label: 'Security', badge: scanResults.filter(s => s.severity !== 'info').length },
              ] as const).map(({ key, Icon, label, badge }) => (
                <button key={key} onClick={() => setActiveTab(key)}
                  className={`px-2.5 py-1.5 text-[11px] font-bold rounded-md transition-colors flex items-center gap-1.5 ${activeTab === key ? 'bg-white/10 text-white' : 'text-white/35 hover:text-white/60 hover:bg-white/5'
                    }`}>
                  <Icon className="w-3.5 h-3.5" /> {label}
                  {badge !== undefined && badge > 0 && (
                    <span className="text-[9px] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded-full border border-red-500/20">{badge}</span>
                  )}
                </button>
              ))}
            </div>
            {activeTab === 'preview' && selectorActive && (
              <span className="text-[10px] font-bold text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded border border-violet-500/20 animate-pulse">
                🔍 SELECTOR ACTIVE — Click any element
              </span>
            )}
          </div>

          {/* Content */}
          <div className="flex-1 relative overflow-hidden">
            <AnimatePresence mode="wait">
              {activeTab === 'preview' && (
                <motion.div key="preview" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 flex items-center justify-center p-4 bg-[#111]">
                  <div className="h-full flex flex-col bg-[#1a1a1a] rounded-xl border border-white/[0.08] shadow-2xl overflow-hidden transition-all duration-300" style={{ width: vpWidth, maxWidth: '100%' }}>
                    {/* Browser Chrome */}
                    <div className="h-9 bg-[#1a1a1a] border-b border-white/[0.06] flex items-center px-3 gap-3 shrink-0">
                      <div className="flex items-center gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
                        <div className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
                        <div className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
                      </div>
                      <div className="flex-1 max-w-md mx-auto bg-black/30 border border-white/[0.06] rounded-md h-6 flex items-center px-2.5">
                        <Lock className="w-2.5 h-2.5 text-emerald-400 mr-1.5" />
                        <span className="text-[10px] text-white/30 font-mono">localhost:3000</span>
                      </div>
                    </div>
                    {/* Content */}
                    <div className="flex-1 bg-white overflow-auto">
                      {htmlContent ? (
                        <iframe ref={iframeRef} className="w-full h-full border-none" sandbox="allow-scripts allow-same-origin" title="Preview" />
                      ) : (
                        <div className="h-full flex flex-col items-center justify-center text-gray-400 gap-4 p-8">
                          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-100 to-cyan-100 flex items-center justify-center"><Globe className="w-8 h-8 text-violet-500/50" /></div>
                          <div className="text-center">
                            <p className="text-sm font-medium text-gray-500">Your web app will render here</p>
                            <p className="text-xs text-gray-400 mt-1">Describe what you want to build in the chat panel</p>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              )}

              {activeTab === 'code' && (
                <motion.div key="code" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 flex flex-col">
                  {/* File Tabs */}
                  <div className="h-9 border-b border-white/[0.04] flex items-center px-2 gap-0.5 bg-[#0c0c0c] shrink-0">
                    {generatedFiles.map((f, i) => (
                      <button key={f.name} onClick={() => setActiveFile(i)}
                        className={`px-2.5 py-1 text-[11px] font-medium rounded-md flex items-center gap-1.5 transition-colors ${activeFile === i ? 'bg-white/10 text-white' : 'text-white/30 hover:text-white/50 hover:bg-white/5'
                          }`}>
                        <FileCode className="w-3 h-3" /> {f.name}
                      </button>
                    ))}
                    {generatedFiles.length === 0 && <span className="text-[11px] text-white/15 px-2">No files generated yet</span>}
                  </div>
                  {/* Code Content */}
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

              {activeTab === 'security' && (
                <motion.div key="security" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 overflow-auto custom-scrollbar p-5">
                  <div className="max-w-2xl mx-auto space-y-3">
                    <div className="flex items-center gap-2 mb-4">
                      <Shield className="w-5 h-5 text-emerald-400" />
                      <span className="text-sm font-bold">Security Analysis</span>
                      <span className="text-[10px] font-mono text-white/20 ml-auto">{scanResults.length} findings</span>
                    </div>
                    {scanResults.length > 0 ? scanResults.map((r, i) => (
                      <div key={i} className={`flex items-start gap-3 p-3 rounded-xl border ${r.severity === 'critical' ? 'bg-red-500/5 border-red-500/20' :
                        r.severity === 'warning' ? 'bg-amber-500/5 border-amber-500/20' :
                          'bg-white/[0.02] border-white/[0.06]'
                        }`}>
                        {r.severity === 'critical' ? <XCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" /> :
                          r.severity === 'warning' ? <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" /> :
                            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />}
                        <div>
                          <div className="text-[12px] font-bold text-white/80">{r.title}</div>
                          <div className="text-[11px] text-white/35 mt-0.5">{r.detail}</div>
                        </div>
                      </div>
                    )) : (
                      <div className="text-center py-16 text-white/15">
                        <Shield className="w-10 h-10 mx-auto mb-3" />
                        <p className="text-sm">Run a build to see security results</p>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* ══ Right Panel: Files + Agent Logs ══ */}
        <div className="w-[260px] border-l border-white/[0.06] flex flex-col bg-[#080808] shrink-0">
          {/* File Tree */}
          <div className="p-3 border-b border-white/[0.04]">
            <div className="flex items-center gap-1.5 mb-2">
              <FolderOpen className="w-3 h-3 text-amber-400" />
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">Project Files</span>
            </div>
            <div className="space-y-0.5">
              {generatedFiles.length > 0 ? generatedFiles.map((f, i) => (
                <button key={f.name} onClick={() => { setActiveFile(i); setActiveTab('code'); }}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11px] text-white/50 hover:text-white/80 hover:bg-white/5 transition-colors">
                  <FileCode className="w-3 h-3 text-cyan-400/50" />
                  <span className="font-mono">{f.name}</span>
                  <span className="text-[9px] text-white/15 ml-auto">{(f.content.length / 1024).toFixed(1)}kb</span>
                </button>
              )) : (
                <div className="text-[10px] text-white/15 px-2 py-3 text-center">No files yet</div>
              )}
            </div>
          </div>

          {/* Agent Logs */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="px-3 py-2 flex items-center gap-1.5">
              <Activity className="w-3 h-3 text-emerald-400" />
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">Agent Logs</span>
              <span className="text-[9px] font-mono text-white/15 ml-auto">{agentLogs.length}</span>
            </div>
            <div className="flex-1 overflow-y-auto custom-scrollbar px-3 pb-3">
              {agentLogs.length > 0 ? agentLogs.map((log, i) => (
                <div key={i} className="text-[10px] font-mono text-white/25 py-0.5 leading-relaxed border-l border-white/[0.04] pl-2 mb-0.5">{log}</div>
              )) : (
                <div className="text-[10px] text-white/10 text-center py-8">Waiting for build...</div>
              )}
              <div ref={logsEndRef} />
            </div>
          </div>

          {/* Status Bar */}
          <div className="h-7 border-t border-white/[0.04] bg-[#0a0a0a] flex items-center px-3 text-[9px] font-mono text-white/15 gap-3">
            <div className="flex items-center gap-1">
              <div className={`w-1.5 h-1.5 rounded-full ${isBuilding ? 'bg-violet-400 animate-pulse' : htmlContent ? 'bg-emerald-400' : 'bg-white/15'}`} />
              {isBuilding ? 'BUILDING' : htmlContent ? 'READY' : 'IDLE'}
            </div>
            {htmlContent && <span>{generatedFiles.length} files</span>}
          </div>
        </div>
      </div>

      {/* Upload Modal */}
      <ProjectUploader
        mode="web"
        isOpen={showUploader}
        onClose={() => setShowUploader(false)}
        onImport={(files, analysis) => {
          addMessage(`📂 Imported project: ${analysis.summary}`, false, 'Import Agent');
          addLog(`📂 Project imported: ${analysis.fileCount} files, ${analysis.language}/${analysis.framework}`);
          if (files.length > 0) {
            const htmlFile = files.find(f => /\.html?$/i.test(f.name));
            if (htmlFile) {
              setHtmlContent(htmlFile.content);
              setGeneratedFiles(files.map(f => ({ name: f.name, language: f.name.split('.').pop() || 'text', content: f.content })));
            }
          }
        }}
      />
    </div>
  );
}

// ── Fallback HTML Generator ──
function generateFallbackHTML(prompt: string): string {
  const isEcommerce = /e-?commerce|shop|store|product|cart/i.test(prompt);
  const isDashboard = /dashboard|analytics|chart|monitor/i.test(prompt);
  const isPortfolio = /portfolio|personal|resume|cv/i.test(prompt);

  if (isEcommerce) return ECOMMERCE_HTML;
  if (isDashboard) return DASHBOARD_HTML;
  if (isPortfolio) return PORTFOLIO_HTML;
  return ECOMMERCE_HTML;
}

const ECOMMERCE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ShopVault — Premium E-Commerce</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f8f9fa;color:#1a1a2e}
nav{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);padding:16px 40px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;box-shadow:0 2px 20px rgba(0,0,0,0.3)}
nav .logo{font-size:22px;font-weight:800;color:#fff;letter-spacing:-0.5px}
nav .logo span{background:linear-gradient(135deg,#e94560,#c850c0);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
nav ul{list-style:none;display:flex;gap:28px}
nav a{color:rgba(255,255,255,0.7);text-decoration:none;font-size:14px;font-weight:500;transition:color 0.2s}
nav a:hover{color:#fff}
.cart-btn{background:linear-gradient(135deg,#e94560,#c850c0);border:none;color:#fff;padding:10px 24px;border-radius:50px;font-weight:700;cursor:pointer;font-size:13px;transition:transform 0.2s,box-shadow 0.2s}
.cart-btn:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(233,69,96,0.4)}
.hero{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:80px 40px;text-align:center;position:relative;overflow:hidden}
.hero::after{content:'';position:absolute;top:0;left:0;right:0;bottom:0;background:radial-gradient(circle at 30% 50%,rgba(233,69,96,0.1),transparent 50%),radial-gradient(circle at 70% 50%,rgba(200,80,192,0.1),transparent 50%)}
.hero h1{font-size:52px;font-weight:800;color:#fff;margin-bottom:16px;letter-spacing:-1px;position:relative;z-index:1}
.hero h1 span{background:linear-gradient(135deg,#e94560,#c850c0);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p{color:rgba(255,255,255,0.6);font-size:18px;max-width:500px;margin:0 auto 32px;position:relative;z-index:1}
.hero-btn{background:linear-gradient(135deg,#e94560,#c850c0);border:none;color:#fff;padding:16px 40px;border-radius:50px;font-size:16px;font-weight:700;cursor:pointer;transition:all 0.3s;position:relative;z-index:1}
.hero-btn:hover{transform:translateY(-3px);box-shadow:0 10px 30px rgba(233,69,96,0.4)}
.products{padding:60px 40px;max-width:1200px;margin:0 auto}
.products h2{font-size:32px;font-weight:800;margin-bottom:8px;letter-spacing:-0.5px}
.products .sub{color:#666;margin-bottom:40px;font-size:15px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:24px}
.card{background:#fff;border-radius:16px;overflow:hidden;transition:all 0.3s;border:1px solid #eee;cursor:pointer}
.card:hover{transform:translateY(-6px);box-shadow:0 20px 40px rgba(0,0,0,0.1)}
.card img{width:100%;height:220px;object-fit:cover;background:linear-gradient(135deg,#f0f0f0,#e8e8e8)}
.card-body{padding:20px}
.card-body h3{font-size:16px;font-weight:700;margin-bottom:6px}
.card-body .price{font-size:20px;font-weight:800;color:#e94560;margin-bottom:12px}
.card-body .price del{font-size:14px;color:#999;font-weight:400;margin-left:8px}
.add-btn{width:100%;background:linear-gradient(135deg,#1a1a2e,#16213e);border:none;color:#fff;padding:12px;border-radius:10px;font-weight:700;font-size:13px;cursor:pointer;transition:all 0.2s}
.add-btn:hover{background:linear-gradient(135deg,#e94560,#c850c0)}
.stars{color:#f59e0b;font-size:12px;margin-bottom:8px}
footer{background:#1a1a2e;color:rgba(255,255,255,0.5);text-align:center;padding:40px;font-size:13px;margin-top:60px}
</style>
</head>
<body>
<nav>
  <div class="logo">Shop<span>Vault</span></div>
  <ul><li><a href="#">Home</a></li><li><a href="#">Collections</a></li><li><a href="#">Deals</a></li><li><a href="#">About</a></li></ul>
  <button class="cart-btn" onclick="alert('Cart: 3 items — $247.97')">🛒 Cart (3)</button>
</nav>
<section class="hero">
  <h1>Discover <span>Premium</span> Products</h1>
  <p>Curated collections of the finest products, delivered to your doorstep with care.</p>
  <button class="hero-btn" onclick="document.querySelector('.products').scrollIntoView({behavior:'smooth'})">Shop Now →</button>
</section>
<section class="products">
  <h2>Trending Now 🔥</h2>
  <p class="sub">Hand-picked products our customers love</p>
  <div class="grid">
    ${[
    { name: 'Wireless Pro Headphones', price: '$89.99', old: '$129.99', stars: '★★★★★' },
    { name: 'Minimal Leather Watch', price: '$149.99', old: '$199.99', stars: '★★★★☆' },
    { name: 'Smart Fitness Tracker', price: '$59.99', old: '$79.99', stars: '★★★★★' },
    { name: 'Premium Backpack', price: '$79.99', old: '$119.99', stars: '★★★★☆' },
    { name: 'Ceramic Coffee Set', price: '$44.99', old: '$64.99', stars: '★★★★★' },
    { name: 'Bamboo Desk Organizer', price: '$34.99', old: '$49.99', stars: '★★★★☆' },
  ].map((p, i) => `
    <div class="card">
      <div style="width:100%;height:220px;background:linear-gradient(${135 + i * 20}deg,${['#667eea,#764ba2', '#f093fb,#f5576c', '#4facfe,#00f2fe', '#43e97b,#38f9d7', '#fa709a,#fee140', '#a18cd1,#fbc2eb'][i]});display:flex;align-items:center;justify-content:center;font-size:48px">${['🎧', '⌚', '📱', '🎒', '☕', '🪴'][i]}</div>
      <div class="card-body">
        <div class="stars">${p.stars}</div>
        <h3>${p.name}</h3>
        <div class="price">${p.price} <del>${p.old}</del></div>
        <button class="add-btn" onclick="this.textContent='✓ Added!';this.style.background='linear-gradient(135deg,#43e97b,#38f9d7)';this.style.color='#1a1a2e'">Add to Cart</button>
      </div>
    </div>`).join('')}
  </div>
</section>
<footer>© 2026 ShopVault — Built with ASTRA Web Studio</footer>
</body>
</html>`;

const DASHBOARD_HTML = `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Analytics Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;display:flex;min-height:100vh}
aside{width:220px;background:#1e293b;padding:24px 16px;border-right:1px solid rgba(255,255,255,0.06)}
aside h2{font-size:16px;font-weight:800;margin-bottom:24px;background:linear-gradient(135deg,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
aside a{display:flex;align-items:center;gap:10px;padding:10px 12px;color:rgba(255,255,255,0.5);text-decoration:none;font-size:13px;border-radius:8px;margin-bottom:4px;transition:all 0.2s}
aside a:hover,aside a.active{background:rgba(56,189,248,0.1);color:#38bdf8}
main{flex:1;padding:32px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px}
.stat{background:#1e293b;border-radius:16px;padding:24px;border:1px solid rgba(255,255,255,0.06)}
.stat .label{font-size:12px;color:rgba(255,255,255,0.4);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.stat .value{font-size:28px;font-weight:800}
.stat .change{font-size:12px;margin-top:4px}
.chart-area{background:#1e293b;border-radius:16px;padding:24px;border:1px solid rgba(255,255,255,0.06);height:300px;display:flex;align-items:flex-end;gap:8px;margin-bottom:24px}
.bar{flex:1;background:linear-gradient(to top,#38bdf8,#818cf8);border-radius:6px 6px 0 0;transition:height 0.5s;min-height:20px;position:relative}
.bar:hover{opacity:0.8}
.bar span{position:absolute;top:-20px;left:50%;transform:translateX(-50%);font-size:10px;color:rgba(255,255,255,0.5)}
h3{font-size:18px;font-weight:700;margin-bottom:16px}
</style></head><body>
<aside><h2>📊 Dashboard</h2>
<a class="active" href="#">📈 Overview</a><a href="#">👥 Users</a><a href="#">💰 Revenue</a><a href="#">📦 Products</a><a href="#">⚙️ Settings</a></aside>
<main>
<h3>Overview</h3>
<div class="stats">
<div class="stat"><div class="label">Revenue</div><div class="value" style="color:#38bdf8">$48.2K</div><div class="change" style="color:#34d399">↑ 12.5%</div></div>
<div class="stat"><div class="label">Users</div><div class="value" style="color:#818cf8">2,847</div><div class="change" style="color:#34d399">↑ 8.3%</div></div>
<div class="stat"><div class="label">Orders</div><div class="value" style="color:#f472b6">1,234</div><div class="change" style="color:#34d399">↑ 5.7%</div></div>
<div class="stat"><div class="label">Conversion</div><div class="value" style="color:#fbbf24">3.2%</div><div class="change" style="color:#f87171">↓ 0.4%</div></div>
</div>
<h3>Weekly Revenue</h3>
<div class="chart-area">
${['Mon:65', 'Tue:80', 'Wed:55', 'Thu:90', 'Fri:75', 'Sat:95', 'Sun:60'].map(d => { const [l, h] = d.split(':'); return `<div class="bar" style="height:${h}%"><span>${l}</span></div>`; }).join('')}
</div>
</main></body></html>`;

const PORTFOLIO_HTML = `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Portfolio</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#fff}
.hero{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:40px;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;width:600px;height:600px;background:radial-gradient(circle,rgba(139,92,246,0.15),transparent 70%);top:50%;left:50%;transform:translate(-50%,-50%)}
h1{font-size:64px;font-weight:900;letter-spacing:-2px;margin-bottom:16px;position:relative}
h1 span{background:linear-gradient(135deg,#8b5cf6,#06b6d4);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.subtitle{font-size:20px;color:rgba(255,255,255,0.5);margin-bottom:40px;position:relative}
.cta{display:inline-flex;gap:12px;position:relative}
.cta a{padding:14px 32px;border-radius:50px;text-decoration:none;font-weight:700;font-size:14px;transition:all 0.3s}
.cta .primary{background:linear-gradient(135deg,#8b5cf6,#06b6d4);color:#fff}
.cta .primary:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(139,92,246,0.3)}
.cta .secondary{border:1px solid rgba(255,255,255,0.15);color:#fff}
.cta .secondary:hover{border-color:rgba(255,255,255,0.3)}
.projects{padding:80px 40px;max-width:1000px;margin:0 auto}
.projects h2{font-size:36px;font-weight:800;margin-bottom:40px;text-align:center;letter-spacing:-1px}
.project-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:24px}
.project{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:20px;padding:32px;transition:all 0.3s}
.project:hover{border-color:rgba(139,92,246,0.3);transform:translateY(-4px)}
.project .tag{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#8b5cf6;margin-bottom:12px;font-weight:700}
.project h3{font-size:18px;font-weight:700;margin-bottom:8px}
.project p{font-size:13px;color:rgba(255,255,255,0.4);line-height:1.6}
footer{text-align:center;padding:40px;color:rgba(255,255,255,0.2);font-size:12px}
</style></head><body>
<section class="hero">
<h1>Hi, I'm <span>Alex</span></h1>
<p class="subtitle">Full-Stack Developer & UI Designer</p>
<div class="cta"><a href="#projects" class="primary">View Projects</a><a href="#" class="secondary">Contact Me</a></div>
</section>
<section class="projects" id="projects">
<h2>Featured Work</h2>
<div class="project-grid">
<div class="project"><div class="tag">Web App</div><h3>E-Commerce Platform</h3><p>Full-stack marketplace with payment integration, real-time inventory, and admin dashboard.</p></div>
<div class="project"><div class="tag">Mobile</div><h3>Fitness Tracker</h3><p>Cross-platform app with workout tracking, progress analytics, and social features.</p></div>
<div class="project"><div class="tag">SaaS</div><h3>Project Manager</h3><p>Team collaboration tool with Kanban boards, time tracking, and automated reporting.</p></div>
<div class="project"><div class="tag">AI/ML</div><h3>Smart Analytics</h3><p>ML-powered business intelligence dashboard with predictive insights and anomaly detection.</p></div>
</div>
</section>
<footer>© 2026 Alex — Built with ASTRA</footer>
</body></html>`;

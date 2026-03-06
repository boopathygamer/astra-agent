import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft, Send, Pencil, X, Check,
  Trash2, Download, MousePointer2, Loader2, ChevronRight, ChevronLeft,
  Sparkles, BookOpen, HelpCircle, Link2, Puzzle, AlertTriangle,
  BarChart3, Gamepad2, Microscope, Calculator, Terminal, Globe,
  PenTool, Database, ListChecks, GraduationCap, Wrench, Trophy,
  FileDown, Flag
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { startTutor, respondTutor } from './api';

// ── Types ──────────────────────────────────────────
type Phase = 'welcome' | 'setup' | 'teaching' | 'finished';

interface Point { x: number; y: number; }
interface TutorMessage { text: string; isUser: boolean; }

interface BoardVisual {
  id: string;
  type: 'concept' | 'formula' | 'step' | 'heading';
  content: string;
  detail?: string;
  color: string;
}

interface LessonEntry {
  role: 'user' | 'tutor';
  text: string;
  visuals: BoardVisual[];
}

// ── Tutor Agents ───────────────────────────────────
const TUTOR_AGENTS = [
  { id: 'feynman', name: 'Feynman', emoji: '🧪', icon: Sparkles, color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20', desc: 'Explain simply' },
  { id: 'scaffolding', name: 'Scaffolding', emoji: '🏗️', icon: BookOpen, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20', desc: 'Build layer by layer' },
  { id: 'socratic', name: 'Socratic', emoji: '🦉', icon: HelpCircle, color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20', desc: 'Guide via questions' },
  { id: 'analogy_bridge', name: 'Analogy', emoji: '🌉', icon: Link2, color: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20', desc: 'Connect unknowns' },
  { id: 'chunking', name: 'Chunking', emoji: '🧩', icon: Puzzle, color: 'text-pink-400', bg: 'bg-pink-500/10', border: 'border-pink-500/20', desc: 'Micro-lessons' },
  { id: 'anti_pattern', name: 'Anti-Pattern', emoji: '🚫', icon: AlertTriangle, color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20', desc: 'Learn from mistakes' },
  { id: 'flowchart', name: 'Flowchart', emoji: '📊', icon: BarChart3, color: 'text-green-400', bg: 'bg-green-500/10', border: 'border-green-500/20', desc: 'Diagram-based' },
  { id: 'game_challenge', name: 'Game', emoji: '🎮', icon: Gamepad2, color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20', desc: 'Gamified quizzes' },
  { id: 'deep_socratic', name: 'Deep Dive', emoji: '🔬', icon: Microscope, color: 'text-violet-400', bg: 'bg-violet-500/10', border: 'border-violet-500/20', desc: 'Research mastery' },
];

const TUTOR_TOOLS = [
  { id: 'calculator', name: 'Calculator', icon: Calculator, color: 'text-emerald-400', hint: 'Calculate: ' },
  { id: 'code_runner', name: 'Code Runner', icon: Terminal, color: 'text-cyan-400', hint: 'Run code: ' },
  { id: 'web_search', name: 'Web Search', icon: Globe, color: 'text-blue-400', hint: 'Search: ' },
  { id: 'writer', name: 'Writer', icon: PenTool, color: 'text-pink-400', hint: 'Write: ' },
  { id: 'data_analyzer', name: 'Analyzer', icon: BarChart3, color: 'text-amber-400', hint: 'Analyze: ' },
  { id: 'knowledge', name: 'Knowledge', icon: Database, color: 'text-purple-400', hint: 'Recall: ' },
  { id: 'task_planner', name: 'Planner', icon: ListChecks, color: 'text-green-400', hint: 'Plan: ' },
];

const DRAW_COLORS = [
  { name: 'Red', value: '#ef4444', tw: 'bg-red-500' },
  { name: 'Blue', value: '#3b82f6', tw: 'bg-blue-500' },
  { name: 'Green', value: '#22c55e', tw: 'bg-green-500' },
  { name: 'Purple', value: '#a855f7', tw: 'bg-purple-500' },
];

const NODE_COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#06b6d4', '#ef4444', '#6366f1'];

// ── Helpers ────────────────────────────────────────

let _vid = 0;
function extractVisuals(text: string): BoardVisual[] {
  const visuals: BoardVisual[] = [];

  // Extract heading-like first sentence or **bold** labels
  const headingMatch = text.match(/^#+\s+(.+)/m) || text.match(/^\*\*(.+?)\*\*/m);
  if (headingMatch) {
    visuals.push({ id: `v${++_vid}`, type: 'heading', content: headingMatch[1].trim(), color: '#f59e0b' });
  }

  // Extract numbered steps → flowchart nodes
  const stepMatches = text.match(/(?:^|\n)\s*\d+[\.\)]\s+.+/g);
  if (stepMatches) {
    stepMatches.slice(0, 6).forEach((s) => {
      const clean = s.replace(/^\s*\d+[\.\)]\s+/, '').replace(/\*\*/g, '').trim();
      if (clean.length > 3 && clean.length < 120) {
        visuals.push({ id: `v${++_vid}`, type: 'step', content: clean, color: NODE_COLORS[visuals.length % NODE_COLORS.length] });
      }
    });
  }

  // Extract formulas (patterns with = sign, math expressions)
  const formulaPatterns = text.match(/[A-Za-z_][\w]*\s*=\s*[^,\n]{2,40}/g);
  if (formulaPatterns) {
    formulaPatterns.slice(0, 4).forEach((f) => {
      const clean = f.replace(/\*\*/g, '').trim();
      if (!visuals.find(v => v.content === clean)) {
        visuals.push({ id: `v${++_vid}`, type: 'formula', content: clean, color: '#a855f7' });
      }
    });
  }

  // Extract key concepts (sentences with "is", "are", definitions)
  const conceptMatches = text.match(/(?:^|\n)\s*[-•]\s+\*\*(.+?)\*\*[:\s]+(.+)/g);
  if (conceptMatches) {
    conceptMatches.slice(0, 4).forEach((c) => {
      const m = c.match(/\*\*(.+?)\*\*[:\s]+(.+)/);
      if (m) {
        visuals.push({ id: `v${++_vid}`, type: 'concept', content: m[1].trim(), detail: m[2].trim().slice(0, 80), color: NODE_COLORS[visuals.length % NODE_COLORS.length] });
      }
    });
  }

  return visuals;
}

function generateLessonHTML(topic: string, log: LessonEntry[], visuals: BoardVisual[]): string {
  const now = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
  const sections = log.map((entry, i) => {
    if (entry.role === 'user') {
      return `<div style="background:#f0fdf4;border-left:4px solid #22c55e;padding:12px 16px;margin:12px 0;border-radius:8px;">
        <strong style="color:#15803d;">You</strong><p style="margin:4px 0 0;color:#333;">${entry.text.replace(/</g, '&lt;')}</p></div>`;
    }
    return `<div style="background:#f8fafc;border-left:4px solid #3b82f6;padding:12px 16px;margin:12px 0;border-radius:8px;">
      <strong style="color:#1d4ed8;">Tutor</strong><pre style="margin:4px 0 0;color:#333;white-space:pre-wrap;font-family:inherit;">${entry.text.replace(/</g, '&lt;')}</pre></div>`;
  }).join('\n');

  const vizSection = visuals.length ? `<h2 style="margin-top:32px;color:#1e293b;">Key Visuals</h2>
    <div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;">
      ${visuals.map(v => `<div style="background:${v.color}15;border:1px solid ${v.color}40;padding:10px 14px;border-radius:10px;min-width:140px;">
        <span style="font-size:10px;text-transform:uppercase;color:${v.color};font-weight:700;">${v.type}</span>
        <p style="margin:4px 0 0;font-weight:600;color:#1e293b;">${v.content.replace(/</g, '&lt;')}</p>
        ${v.detail ? `<p style="margin:2px 0 0;font-size:13px;color:#64748b;">${v.detail.replace(/</g, '&lt;')}</p>` : ''}
      </div>`).join('')}
    </div>` : '';

  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Lesson: ${topic}</title>
    <style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:800px;margin:0 auto;padding:40px 24px;color:#1e293b;line-height:1.6;}
    h1{font-size:28px;margin-bottom:4px;}h2{font-size:20px;color:#334155;border-bottom:1px solid #e2e8f0;padding-bottom:8px;}
    .meta{color:#94a3b8;font-size:14px;margin-bottom:32px;}
    @media print{body{padding:20px;}}</style></head>
    <body><h1>📚 ${topic}</h1><p class="meta">${now} · Astra Agent Tutor</p>
    <h2>Lesson Transcript</h2>${sections}${vizSection}
    <hr style="margin-top:40px;border:none;border-top:1px solid #e2e8f0;">
    <p style="text-align:center;color:#94a3b8;font-size:13px;">Generated by Astra Agent Tutor</p></body></html>`;
}

// ── Component ──────────────────────────────────────

export default function TutorPage() {
  // ── Phase / Session ──
  const [phase, setPhase] = useState<Phase>('welcome');
  const [topic, setTopic] = useState('');
  const [topicInput, setTopicInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);

  // ── Chat ──
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ── Board Visuals ──
  const [boardVisuals, setBoardVisuals] = useState<BoardVisual[]>([]);

  // ── Lesson Log (for PDF) ──
  const [lessonLog, setLessonLog] = useState<LessonEntry[]>([]);

  // ── Drawing ──
  const [isDrawingMode, setIsDrawingMode] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [selectedColor, setSelectedColor] = useState('#ef4444');
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const contextRef = useRef<CanvasRenderingContext2D | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const pointsRef = useRef<Point[]>([]);

  // ── Sidebar ──
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  const [activeTechnique, setActiveTechnique] = useState<string | null>(null);
  const [panelTab, setPanelTab] = useState<'agents' | 'tools'>('agents');

  // ── Canvas Init ──
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;

    const resizeCanvas = () => {
      const { width, height } = parent.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.scale(dpr, dpr);
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.strokeStyle = selectedColor;
        ctx.lineWidth = 3;
        contextRef.current = ctx;
      }
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    return () => window.removeEventListener('resize', resizeCanvas);
  }, [phase]);

  useEffect(() => {
    if (contextRef.current) contextRef.current.strokeStyle = selectedColor;
  }, [selectedColor]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Drawing Handlers ──
  const getCoords = (e: React.MouseEvent | React.TouchEvent): Point => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    if ('nativeEvent' in e && e.nativeEvent instanceof MouseEvent) {
      return { x: e.nativeEvent.clientX - rect.left, y: e.nativeEvent.clientY - rect.top };
    }
    const touch = (e as React.TouchEvent).touches[0];
    return { x: touch.clientX - rect.left, y: touch.clientY - rect.top };
  };

  const startDraw = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isDrawingMode) return;
    const p = getCoords(e);
    setIsDrawing(true);
    pointsRef.current = [p];
    contextRef.current?.beginPath();
    contextRef.current?.moveTo(p.x, p.y);
  };

  const drawMove = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isDrawing || !isDrawingMode || !contextRef.current) return;
    const p = getCoords(e);
    pointsRef.current.push(p);
    const pts = pointsRef.current;
    if (pts.length > 2) {
      const a = pts[pts.length - 2], b = pts[pts.length - 1];
      contextRef.current.quadraticCurveTo(a.x, a.y, (a.x + b.x) / 2, (a.y + b.y) / 2);
      contextRef.current.stroke();
    }
  };

  const stopDraw = () => { if (isDrawing) { setIsDrawing(false); pointsRef.current = []; contextRef.current?.closePath(); } };

  const clearCanvas = () => {
    const c = canvasRef.current, ctx = contextRef.current;
    if (c && ctx) ctx.clearRect(0, 0, c.width, c.height);
  };

  // ── Phase Handlers ──
  const handleTopicSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topicInput.trim()) return;
    const t = topicInput.trim();
    setTopic(t);
    setPhase('setup');

    // Brief setup animation, then start session
    setTimeout(async () => {
      try {
        const prefix = activeTechnique ? `[technique:${activeTechnique}] ` : '';
        const res = await startTutor(prefix + t);
        setSessionId(res.session_id);
        const greeting = res.greeting || res.response || `Let's learn about ${t}!`;
        setMessages([{ text: greeting, isUser: false }]);
        const vis = extractVisuals(greeting);
        setBoardVisuals(vis);
        setLessonLog([{ role: 'tutor', text: greeting, visuals: vis }]);
        setPhase('teaching');
      } catch {
        setMessages([{ text: `Let's learn about ${t}! Ask me anything to get started.`, isUser: false }]);
        setPhase('teaching');
      }
    }, 1500);
  }, [topicInput, activeTechnique]);

  const handleChatSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    const text = input.trim();
    setMessages(prev => [...prev, { text, isUser: true }]);
    setLessonLog(prev => [...prev, { role: 'user', text, visuals: [] }]);
    setInput('');
    setIsLoading(true);

    try {
      if (!sessionId) {
        const prefix = activeTechnique ? `[technique:${activeTechnique}] ` : '';
        const res = await startTutor(prefix + text);
        setSessionId(res.session_id);
        const reply = res.greeting || res.response || JSON.stringify(res);
        setMessages(prev => [...prev, { text: reply, isUser: false }]);
        const vis = extractVisuals(reply);
        setBoardVisuals(prev => [...prev, ...vis]);
        setLessonLog(prev => [...prev, { role: 'tutor', text: reply, visuals: vis }]);
      } else {
        const res = await respondTutor(sessionId, text);
        const reply = res.response || JSON.stringify(res);
        setMessages(prev => [...prev, { text: reply, isUser: false }]);
        const vis = extractVisuals(reply);
        setBoardVisuals(prev => [...prev, ...vis]);
        setLessonLog(prev => [...prev, { role: 'tutor', text: reply, visuals: vis }]);
      }
    } catch (err: any) {
      const errMsg = `⚠️ ${err?.message || 'Failed to reach the tutor.'}`;
      setMessages(prev => [...prev, { text: errMsg, isUser: false }]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, sessionId, activeTechnique]);

  const handleFinishClass = useCallback(() => {
    setPhase('finished');
  }, []);

  const handleDownloadPDF = useCallback(() => {
    const html = generateLessonHTML(topic, lessonLog, boardVisuals);
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Lesson_${topic.replace(/\s+/g, '_')}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }, [topic, lessonLog, boardVisuals]);

  const handleSelectTechnique = useCallback((id: string) => {
    setActiveTechnique(prev => prev === id ? null : id);
  }, []);

  const handleSelectTool = useCallback((hint: string) => {
    setInput(prev => prev || hint);
  }, []);

  // ═══════════════════════════ RENDER ═══════════════════════════

  // ── Welcome Phase ──
  if (phase === 'welcome') {
    return (
      <div className="h-screen bg-[#0a0a0a] text-white flex overflow-hidden selection:bg-emerald-500/30">
        {/* Sidebar */}
        <AnimatePresence mode="wait">
          {isSidebarOpen && (
            <motion.div initial={{ width: 0, opacity: 0 }} animate={{ width: 260, opacity: 1 }} exit={{ width: 0, opacity: 0 }}
              className="h-full bg-[#0c0c0c] border-r border-white/10 flex flex-col overflow-hidden flex-shrink-0">
              <div className="px-4 pt-4 pb-3 border-b border-white/5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 bg-emerald-500/10 rounded-lg border border-emerald-500/20"><GraduationCap className="w-4 h-4 text-emerald-400" /></div>
                    <span className="text-sm font-bold text-white/90">Tutor Hub</span>
                  </div>
                  <button onClick={() => setSidebarOpen(false)} className="p-1.5 text-white/30 hover:text-white hover:bg-white/5 rounded-lg transition-colors"><ChevronLeft className="w-4 h-4" /></button>
                </div>
                <div className="flex gap-1 bg-white/[0.03] p-0.5 rounded-lg">
                  <button onClick={() => setPanelTab('agents')} className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-bold uppercase tracking-wider transition-all ${panelTab === 'agents' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20' : 'text-white/30 hover:text-white/60'}`}>
                    <Trophy className="w-3 h-3" /> Agents
                  </button>
                  <button onClick={() => setPanelTab('tools')} className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-bold uppercase tracking-wider transition-all ${panelTab === 'tools' ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/20' : 'text-white/30 hover:text-white/60'}`}>
                    <Wrench className="w-3 h-3" /> Tools
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto custom-scrollbar px-3 py-2 space-y-0.5">
                {panelTab === 'agents' ? TUTOR_AGENTS.map(agent => {
                  const Icon = agent.icon;
                  const active = activeTechnique === agent.id;
                  return (
                    <button key={agent.id} onClick={() => handleSelectTechnique(agent.id)}
                      className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-left transition-all ${active ? `${agent.bg} ${agent.border} border` : 'hover:bg-white/[0.04] border border-transparent'}`}>
                      <div className={`p-1 rounded-lg ${active ? agent.bg : 'bg-white/[0.04]'}`}><Icon className={`w-3.5 h-3.5 ${active ? agent.color : 'text-white/40'}`} /></div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1"><span className="text-[10px]">{agent.emoji}</span><span className={`text-xs font-semibold ${active ? 'text-white' : 'text-white/70'}`}>{agent.name}</span></div>
                        <p className="text-[9px] text-white/20 truncate">{agent.desc}</p>
                      </div>
                      {active && <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.5)]" />}
                    </button>
                  );
                }) : TUTOR_TOOLS.map(tool => {
                  const Icon = tool.icon;
                  return (
                    <button key={tool.id} onClick={() => handleSelectTool(tool.hint)}
                      className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-left hover:bg-white/[0.04] transition-all">
                      <div className="p-1 rounded-lg bg-white/[0.04]"><Icon className={`w-3.5 h-3.5 ${tool.color}`} /></div>
                      <span className="text-xs font-semibold text-white/70">{tool.name}</span>
                    </button>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Welcome Center */}
        <div className="flex-1 flex flex-col items-center justify-center px-6 relative">
          {!isSidebarOpen && (
            <button onClick={() => setSidebarOpen(true)} className="absolute top-4 left-4 p-2 text-white/30 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
              <ChevronRight className="w-4 h-4" />
            </button>
          )}
          <Link to="/chat" className="absolute top-4 right-4 flex items-center gap-2 text-white/40 hover:text-white transition-colors text-sm">
            <ArrowLeft className="w-4 h-4" /> Back
          </Link>

          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}
            className="text-center max-w-lg">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 border border-emerald-500/20 flex items-center justify-center mx-auto mb-6 shadow-[0_0_40px_rgba(16,185,129,0.15)]">
              <GraduationCap className="w-10 h-10 text-emerald-400" />
            </div>
            <h1 className="text-3xl font-bold text-white mb-2 tracking-tight">What topic should I teach?</h1>
            <p className="text-white/40 text-sm mb-8">Enter any subject and I'll prepare an interactive visual lesson for you.</p>

            {activeTechnique && (
              <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold mb-4">
                {TUTOR_AGENTS.find(a => a.id === activeTechnique)?.emoji} {TUTOR_AGENTS.find(a => a.id === activeTechnique)?.name} technique selected
              </motion.div>
            )}

            <form onSubmit={handleTopicSubmit} className="flex gap-3">
              <input
                type="text"
                value={topicInput}
                onChange={e => setTopicInput(e.target.value)}
                placeholder="e.g. Newton's Laws, Binary Search, Photosynthesis..."
                className="flex-1 bg-white/5 border border-white/10 focus:border-emerald-500/50 rounded-xl px-5 py-3.5 text-white placeholder-white/20 outline-none transition-all text-sm"
                autoFocus
              />
              <button type="submit" disabled={!topicInput.trim()}
                className="px-6 py-3.5 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-30 disabled:cursor-not-allowed text-black font-bold rounded-xl transition-all shadow-[0_0_20px_rgba(16,185,129,0.2)] flex items-center gap-2">
                <Send className="w-4 h-4" /> Start
              </button>
            </form>
          </motion.div>
        </div>
      </div>
    );
  }

  // ── Setup Phase ──
  if (phase === 'setup') {
    return (
      <div className="h-screen bg-[#0a0a0a] text-white flex items-center justify-center overflow-hidden">
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} className="text-center">
          <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 2, ease: 'linear' }}
            className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 border border-emerald-500/20 flex items-center justify-center mx-auto mb-6">
            <Loader2 className="w-8 h-8 text-emerald-400" />
          </motion.div>
          <h2 className="text-xl font-bold text-white mb-2">Preparing your lesson</h2>
          <p className="text-white/40 text-sm">{topic}</p>
          <div className="flex items-center justify-center gap-1 mt-4">
            {[0, 1, 2].map(i => (
              <motion.div key={i} animate={{ opacity: [0.2, 1, 0.2] }} transition={{ repeat: Infinity, duration: 1.2, delay: i * 0.3 }}
                className="w-2 h-2 rounded-full bg-emerald-400" />
            ))}
          </div>
        </motion.div>
      </div>
    );
  }

  // ── Finished Phase Overlay ──
  if (phase === 'finished') {
    return (
      <div className="h-screen bg-[#0a0a0a] text-white flex items-center justify-center overflow-hidden">
        <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} className="text-center max-w-md">
          <div className="w-20 h-20 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto mb-6 shadow-[0_0_40px_rgba(16,185,129,0.2)]">
            <Trophy className="w-10 h-10 text-emerald-400" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">Class Complete! 🎉</h2>
          <p className="text-white/50 text-sm mb-2">Topic: <span className="text-emerald-400 font-medium">{topic}</span></p>
          <p className="text-white/30 text-xs mb-8">{messages.length} messages · {boardVisuals.length} visual elements</p>

          <button onClick={handleDownloadPDF}
            className="px-8 py-3.5 bg-emerald-500 hover:bg-emerald-400 text-black font-bold rounded-xl transition-all shadow-[0_0_30px_rgba(16,185,129,0.3)] flex items-center gap-2 mx-auto mb-4">
            <FileDown className="w-5 h-5" /> Download Lesson Notes
          </button>

          <Link to="/chat" className="text-white/40 hover:text-white text-sm transition-colors inline-flex items-center gap-1">
            <ArrowLeft className="w-3 h-3" /> Back to Chat
          </Link>
        </motion.div>
      </div>
    );
  }

  // ══════════════════════════════════════════════════
  // ── Teaching Phase — Main Layout ──
  // ══════════════════════════════════════════════════
  return (
    <div className="h-screen bg-[#0a0a0a] text-white flex overflow-hidden selection:bg-emerald-500/30">

      {/* ── Sidebar ── */}
      <AnimatePresence mode="wait">
        {isSidebarOpen && (
          <motion.div initial={{ width: 0, opacity: 0 }} animate={{ width: 240, opacity: 1 }} exit={{ width: 0, opacity: 0 }}
            className="h-full bg-[#0c0c0c] border-r border-white/10 flex flex-col overflow-hidden flex-shrink-0">
            <div className="px-3 pt-3 pb-2 border-b border-white/5">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="p-1 bg-emerald-500/10 rounded-md border border-emerald-500/20"><GraduationCap className="w-3.5 h-3.5 text-emerald-400" /></div>
                  <span className="text-xs font-bold text-white/90">Tutor Hub</span>
                </div>
                <button onClick={() => setSidebarOpen(false)} className="p-1 text-white/30 hover:text-white rounded transition-colors"><ChevronLeft className="w-3.5 h-3.5" /></button>
              </div>
              <div className="flex gap-1 bg-white/[0.03] p-0.5 rounded-lg">
                <button onClick={() => setPanelTab('agents')} className={`flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all ${panelTab === 'agents' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20' : 'text-white/30 hover:text-white/60'}`}>
                  <Trophy className="w-2.5 h-2.5" /> Agents
                </button>
                <button onClick={() => setPanelTab('tools')} className={`flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all ${panelTab === 'tools' ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/20' : 'text-white/30 hover:text-white/60'}`}>
                  <Wrench className="w-2.5 h-2.5" /> Tools
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto custom-scrollbar px-2 py-2 space-y-0.5">
              {panelTab === 'agents' ? TUTOR_AGENTS.map(agent => {
                const Icon = agent.icon;
                const active = activeTechnique === agent.id;
                return (
                  <button key={agent.id} onClick={() => handleSelectTechnique(agent.id)}
                    className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-all ${active ? `${agent.bg} ${agent.border} border` : 'hover:bg-white/[0.04] border border-transparent'}`}>
                    <Icon className={`w-3 h-3 ${active ? agent.color : 'text-white/40'}`} />
                    <span className={`text-[11px] font-semibold ${active ? 'text-white' : 'text-white/60'}`}>{agent.emoji} {agent.name}</span>
                    {active && <div className="ml-auto w-1 h-1 rounded-full bg-emerald-400" />}
                  </button>
                );
              }) : TUTOR_TOOLS.map(tool => {
                const Icon = tool.icon;
                return (
                  <button key={tool.id} onClick={() => handleSelectTool(tool.hint)}
                    className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left hover:bg-white/[0.04] transition-all">
                    <Icon className={`w-3 h-3 ${tool.color}`} />
                    <span className="text-[11px] font-semibold text-white/60">{tool.name}</span>
                  </button>
                );
              })}
            </div>
            {activeTechnique && (
              <div className="px-3 py-2 border-t border-white/5 bg-emerald-500/[0.03]">
                <div className="flex items-center gap-1.5">
                  <div className="w-1 h-1 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-[9px] font-bold text-emerald-400/80 uppercase tracking-wider">
                    {TUTOR_AGENTS.find(a => a.id === activeTechnique)?.emoji} {TUTOR_AGENTS.find(a => a.id === activeTechnique)?.name}
                  </span>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Main Content: Board + Chat side by side ── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* ── Compact Header ── */}
        <header className="h-10 flex items-center justify-between px-3 border-b border-white/5 flex-shrink-0 bg-[#0a0a0a]">
          <div className="flex items-center gap-2">
            {!isSidebarOpen && (
              <button onClick={() => setSidebarOpen(true)} className="p-1 text-white/30 hover:text-white rounded transition-colors"><ChevronRight className="w-3.5 h-3.5" /></button>
            )}
            <Link to="/chat" className="flex items-center gap-1.5 text-white/40 hover:text-white transition-colors text-xs">
              <ArrowLeft className="w-3 h-3" /> Back
            </Link>
            <span className="text-[10px] text-white/20 font-mono ml-2 truncate max-w-[200px]">{topic}</span>
          </div>

          <div className="flex items-center gap-1.5">
            {/* Drawing tools */}
            <AnimatePresence>
              {isDrawingMode && (
                <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }}
                  className="flex items-center gap-1 bg-white/5 p-0.5 rounded-lg border border-white/10">
                  {DRAW_COLORS.map(c => (
                    <button key={c.name} onClick={() => { setSelectedColor(c.value); }}
                      className={`w-4 h-4 rounded-full ${c.tw} transition-all ${selectedColor === c.value ? 'ring-2 ring-white/50 scale-110' : 'ring-1 ring-black/20 opacity-60 hover:opacity-100'}`}
                    />
                  ))}
                  <button onClick={clearCanvas} className="p-1 text-white/40 hover:text-red-400 rounded transition-colors"><Trash2 className="w-3 h-3" /></button>
                  <button onClick={() => setIsDrawingMode(false)} className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-bold bg-white text-black rounded-md hover:bg-gray-200 transition-colors">
                    <MousePointer2 className="w-2.5 h-2.5" /> Exit
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            {!isDrawingMode && (
              <button onClick={() => setIsDrawingMode(true)}
                className="p-1.5 text-white/30 hover:text-emerald-400 hover:bg-white/5 rounded-lg transition-colors relative">
                <Pencil className="w-3.5 h-3.5" />
                <div className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
              </button>
            )}

            <button onClick={handleFinishClass}
              className="flex items-center gap-1 px-2.5 py-1 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 text-[10px] font-bold uppercase tracking-wider rounded-lg transition-colors">
              <Flag className="w-3 h-3" /> Finish Class
            </button>
          </div>
        </header>

        {/* ── Board + Chat ── */}
        <div className="flex-1 flex min-h-0">

          {/* ── Board Panel (left) ── */}
          <div className="flex-[3] flex flex-col border-r border-white/5 min-w-0 relative">
            <div className="flex-1 relative bg-white overflow-hidden">
              {/* Grid pattern */}
              <div className="absolute inset-0 opacity-[0.03] pointer-events-none"
                style={{ backgroundImage: 'linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)', backgroundSize: '28px 28px' }} />

              {/* Canvas (sketching) */}
              <canvas ref={canvasRef}
                onMouseDown={startDraw} onMouseMove={drawMove} onMouseUp={stopDraw} onMouseLeave={stopDraw}
                onTouchStart={startDraw} onTouchMove={drawMove} onTouchEnd={stopDraw}
                className={`absolute inset-0 w-full h-full touch-none ${isDrawingMode ? 'cursor-crosshair z-30' : 'cursor-default z-10'}`}
              />

              {/* Agent Visuals Overlay */}
              <div className="absolute inset-0 z-20 pointer-events-none p-4 overflow-hidden">
                {boardVisuals.length === 0 && !isDrawingMode && (
                  <div className="h-full flex items-center justify-center">
                    <span className="text-black/[0.06] font-serif italic text-5xl tracking-tight rotate-[-3deg] select-none">Astra Board</span>
                  </div>
                )}

                {boardVisuals.length > 0 && (
                  <div className="h-full flex flex-col gap-2 overflow-y-auto custom-scrollbar pointer-events-auto pr-1">
                    {/* Heading visuals */}
                    {boardVisuals.filter(v => v.type === 'heading').map((v, i) => (
                      <motion.div key={v.id} initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
                        className="text-center mb-1">
                        <span className="inline-block px-4 py-1.5 bg-amber-50 border border-amber-200 rounded-full text-amber-800 font-bold text-sm shadow-sm">
                          {v.content}
                        </span>
                      </motion.div>
                    ))}

                    {/* Flow: Steps as connected nodes */}
                    {boardVisuals.filter(v => v.type === 'step').length > 0 && (
                      <div className="flex flex-wrap items-start gap-2 mt-1">
                        {boardVisuals.filter(v => v.type === 'step').map((v, i, arr) => (
                          <React.Fragment key={v.id}>
                            <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
                              transition={{ delay: 0.15 + i * 0.12, type: 'spring', stiffness: 300 }}
                              className="flex-shrink-0 max-w-[220px]">
                              <div className="relative bg-white rounded-xl border-2 shadow-md px-3 py-2" style={{ borderColor: v.color }}>
                                <div className="absolute -top-2.5 -left-1 w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-black text-white shadow" style={{ background: v.color }}>
                                  {i + 1}
                                </div>
                                <p className="text-gray-700 text-[11px] leading-snug font-medium pl-3">{v.content}</p>
                              </div>
                            </motion.div>
                            {i < arr.length - 1 && (
                              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 + i * 0.12 }}
                                className="flex items-center self-center text-gray-300 flex-shrink-0">
                                <svg width="24" height="12" viewBox="0 0 24 12"><path d="M0 6h18M14 1l6 5-6 5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                              </motion.div>
                            )}
                          </React.Fragment>
                        ))}
                      </div>
                    )}

                    {/* Formulas */}
                    {boardVisuals.filter(v => v.type === 'formula').length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-1">
                        {boardVisuals.filter(v => v.type === 'formula').map((v, i) => (
                          <motion.div key={v.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 + i * 0.1 }}
                            className="bg-purple-50 border border-purple-200 rounded-xl px-4 py-2 shadow-sm">
                            <span className="text-[8px] font-bold uppercase tracking-widest text-purple-400">Formula</span>
                            <p className="text-purple-900 font-mono font-bold text-sm mt-0.5">{v.content}</p>
                          </motion.div>
                        ))}
                      </div>
                    )}

                    {/* Concepts */}
                    {boardVisuals.filter(v => v.type === 'concept').length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-1">
                        {boardVisuals.filter(v => v.type === 'concept').map((v, i) => (
                          <motion.div key={v.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 + i * 0.1 }}
                            className="bg-white rounded-xl border shadow-sm px-3 py-2 max-w-[200px]" style={{ borderColor: v.color + '60' }}>
                            <div className="flex items-center gap-1.5 mb-0.5">
                              <div className="w-2 h-2 rounded-full" style={{ background: v.color }} />
                              <span className="font-bold text-gray-800 text-xs">{v.content}</span>
                            </div>
                            {v.detail && <p className="text-gray-500 text-[10px] leading-snug">{v.detail}</p>}
                          </motion.div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ── Chat Panel (right) ── */}
          <div className="flex-[2] flex flex-col min-w-0 bg-[#0d0d0d]">
            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto custom-scrollbar px-3 py-3 space-y-3">
              {messages.map((msg, idx) => (
                <motion.div key={idx} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                  className={`flex ${msg.isUser ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[90%] rounded-2xl px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap ${msg.isUser
                    ? 'bg-emerald-500 text-black font-medium rounded-br-md'
                    : 'bg-white/[0.06] text-white/80 border border-white/5 rounded-bl-md'
                    }`}>
                    {msg.text}
                  </div>
                </motion.div>
              ))}
              {isLoading && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-2 bg-white/[0.06] text-white/40 rounded-2xl px-3 py-2 text-xs border border-white/5">
                    <Loader2 className="w-3 h-3 animate-spin" /> Thinking...
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Compact Input */}
            <form onSubmit={handleChatSubmit} className="flex-shrink-0 px-3 pb-3 pt-1">
              <div className="flex items-center gap-2 bg-white/[0.05] border border-white/10 rounded-xl px-3 py-2 focus-within:border-emerald-500/30 transition-all">
                <input
                  type="text"
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  placeholder={sessionId ? 'Ask a question...' : 'Type to start...'}
                  className="flex-1 bg-transparent border-none outline-none text-white placeholder-white/20 text-[13px]"
                />
                <button type="submit" disabled={!input.trim() || isLoading}
                  className={`p-1.5 rounded-lg transition-all ${input.trim() && !isLoading ? 'bg-emerald-500 text-black hover:bg-emerald-400' : 'bg-white/5 text-white/15 cursor-not-allowed'}`}>
                  {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}

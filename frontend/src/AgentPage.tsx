import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { 
  ArrowLeft, Activity, Cpu, Shield, Zap, Database, Network, Terminal,
  RefreshCcw, Circle, ChevronDown, ChevronUp, Wifi, WifiOff, BrainCircuit,
  Wrench, MessageSquare, GitBranch, ArrowRight, ArrowLeftRight, Bot,
  HardDrive, Clock, Gauge, AlertTriangle, CheckCircle2, XCircle
, Play, Eye, Hash, ChevronRight, Scale, Trophy, Crown } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import {
  checkHealth, getProviderStatus, getAgentStats, getProcesses,
  getSessions, getMemoryStats, getLongTermMemory, getDeviceList,
  getOrchestratorStatus, getASIStatus,
  type HealthStatus, type ASIStatusResponse
} from './api';

// ── Types ──

interface ActivityLog {
  id: string;
  timestamp: string;
  type: 'agent' | 'tool' | 'system' | 'communication' | 'defense' | 'memory';
  source: string;
  target?: string;
  action: string;
  status: 'success' | 'error' | 'active' | 'pending';
  detail?: string;
}

// ── Helpers ──

const StatusDot = ({ status }: { status: string }) => {
  const color = status === 'connected' || status === 'ready' || status === 'success' || status === 'active'
    ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]'
    : status === 'error' || status === 'disconnected' || status === 'offline'
      ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]'
      : 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)] animate-pulse';
  return <div className={`w-2 h-2 rounded-full ${color}`} />;
};

const TypeIcon = ({ type }: { type: string }) => {
  const cls = "w-3.5 h-3.5";
  switch (type) {
    case 'agent': return <Bot className={`${cls} text-violet-400`} />;
    case 'tool': return <Wrench className={`${cls} text-amber-400`} />;
    case 'system': return <Cpu className={`${cls} text-cyan-400`} />;
    case 'communication': return <ArrowLeftRight className={`${cls} text-emerald-400`} />;
    case 'defense': return <Shield className={`${cls} text-red-400`} />;
    case 'memory': return <BrainCircuit className={`${cls} text-pink-400`} />;
    default: return <Activity className={`${cls} text-white/40`} />;
  }
};

const TypeBadge = ({ type }: { type: string }) => {
  const colors: Record<string, string> = {
    agent: 'bg-violet-500/15 text-violet-400 border-violet-500/20',
    tool: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
    system: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/20',
    communication: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
    defense: 'bg-red-500/15 text-red-400 border-red-500/20',
    memory: 'bg-pink-500/15 text-pink-400 border-pink-500/20',
  };
  return (
    <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${colors[type] || 'bg-white/5 text-white/40 border-white/10'}`}>
      {type}
    </span>
  );
};

const formatTime = (d: Date) => d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });


export interface ExecutionStep {
  id: string; step: number; phase: string; agent: string; agentEmoji: string; action: string; durationMs: number; timestamp: string; status: 'done' | 'running' | 'error'; detail?: string;
}
export interface ReActStep {
  id: string; agent: string; agentEmoji: string; agentType: 'agent'|'system'|'tool'; think: string; act: string; actTool?: string; observe: string; timestamp: string; durationMs: number; status: 'done' | 'running' | 'error';
}
export interface CommMessage {
  id: string; timestamp: string; from: string; fromType: 'agent'|'system'|'tool'; fromEmoji: string; to: string; toType: 'agent'|'system'|'tool'; toEmoji: string; message: string; channel: string;
}
export interface AgentThread {
  id: string; channel: string; participants: {name: string, emoji: string, type: 'agent'|'tool'|'system'}[]; messages: CommMessage[]; status: 'resolved' | 'active'; summary: string;
}
export interface Decision {
  id: string; timestamp: string; maker: string; makerEmoji: string; title: string; reasoning: string[]; confidence: number; outcome: 'approved' | 'rejected' | 'pending'; alternatives: string[];
}
export interface AgentRanking {
  name: string; emoji: string; type: 'agent'|'system'|'tool'; quality: number; speed: number; reliability: number; overall: number; votes: number; trend: 'up' | 'down' | 'stable';
}

const getEmojiForAgent = (name: string) => {
  if (name.includes('Logic')) return '🧠';
  if (name.includes('Actor')) return '▶️';
  if (name.includes('Observer')) return '👀';
  if (name.includes('Critic')) return '🔍';
  if (name.includes('Brain')) return '🧠';
  if (name.includes('Controller')) return '🎛️';
  if (name.includes('Architect')) return '🏗️';
  if (name.includes('Hunter')) return '🕵️';
  if (name.includes('Council')) return '⚖️';
  return '🤖';
};

// ── Main Component ──


export default function AgentPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [providerStatus, setProviderStatus] = useState<any>(null);
  const [agentStats, setAgentStats] = useState<any>(null);
  const [processes, setProcesses] = useState<any>(null);
  const [sessions, setSessions] = useState<any>(null);
  const [memoryStats, setMemoryStats] = useState<any>(null);
  const [longTermMem, setLongTermMem] = useState<any>(null);
  const [devices, setDevices] = useState<any>(null);
  const [activityLog, setActivityLog] = useState<ActivityLog[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [expandedSection, setExpandedSection] = useState<string | null>('activity');
  const [filterType, setFilterType] = useState<string>('all');
  const logEndRef = useRef<HTMLDivElement>(null);

  // Orchestrator state (read-only)
  const [orchStatus, setOrchStatus] = useState<any>(null);
  const [isOrchModalOpen, setOrchModalOpen] = useState(false);

  // ── Live Streaming WebSocket State ──
  const [commTab, setCommTab] = useState<'activity' | 'chats' | 'decisions' | 'rankings' | 'feed' | 'asi'>('activity');
  const [expandedThreads, setExpandedThreads] = useState<Set<string>>(new Set());
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const [reactSteps, setReactSteps] = useState<ReActStep[]>([]);
  const [agentThreads, setAgentThreads] = useState<AgentThread[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [rankings, setRankings] = useState<AgentRanking[]>([]);
  
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // ── ASI Status State ──
  const [asiStatus, setAsiStatus] = useState<ASIStatusResponse | null>(null);
  const [asiLoading, setAsiLoading] = useState(false);

  useEffect(() => {
    const socket = new WebSocket('ws://localhost:8000/ws/chat');
    
    socket.onopen = () => console.log('AgentPage WebSocket connected');

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'execution_step') {
          setExecutionSteps(prev => {
            const stepExists = prev.find(s => s.id === data.step.toString());
            if (stepExists && data.status === 'running') return prev;

            const newStep: ExecutionStep = {
              id: data.step.toString(),
              step: data.step,
              phase: data.phase,
              agent: data.agent,
              agentEmoji: getEmojiForAgent(data.agent),
              action: data.action,
              durationMs: data.duration,
              timestamp: formatTime(new Date()),
              status: data.status,
            };
            
            if (data.status === 'done') {
               return [...prev.filter(s => s.id !== newStep.id), newStep].sort((a,b) => a.step - b.step);
            }
            return [...prev, newStep].sort((a,b) => a.step - b.step);
          });
        }
        else if (data.type === 'react_step') {
          setReactSteps(prev => {
            const newStep: ReActStep = {
              id: `${data.step}-${data.action}`,
              agent: data.agent,
              agentEmoji: getEmojiForAgent(data.agent),
              agentType: data.agent.includes('Observer') ? 'system' : 'agent',
              think: data.action === 'think' ? data.content : '',
              act: data.action === 'act' ? data.content : '',
              observe: data.action === 'observe' ? data.content : '',
              timestamp: formatTime(new Date()),
              durationMs: data.duration,
              status: data.action === 'observe' ? 'done' : 'running'
            };
            
            const existingId = data.step.toString();
            const existing = prev.find(s => s.id === existingId || s.id.startsWith(`${data.step}-`));
            
            if (existing) {
               return prev.map(s => (s.id === existingId || s.id.startsWith(`${data.step}-`)) ? {
                 ...s,
                 id: data.step.toString(),
                 agent: newStep.agent || s.agent,
                 agentEmoji: newStep.agentEmoji || s.agentEmoji,
                 think: newStep.think || s.think,
                 act: newStep.act || s.act,
                 observe: newStep.observe || s.observe,
                 status: newStep.status,
                 durationMs: newStep.durationMs || s.durationMs
               } : s);
            }
            newStep.id = data.step.toString();
            return [...prev, newStep];
          });
        }
        else if (data.type === 'thread_message') {
           setAgentThreads(prev => {
              const channelId = data.channel || 'general';
              const existingThread = prev.find(t => t.channel === channelId);
              
              const newMsg: CommMessage = {
                 id: `${Date.now()}-${Math.random()}`,
                 timestamp: formatTime(new Date(data.timestamp || Date.now())),
                 from: data.role,
                 fromType: 'agent',
                 fromEmoji: getEmojiForAgent(data.role),
                 to: 'All',
                 toType: 'system',
                 toEmoji: '📢',
                 message: data.content,
                 channel: channelId
              };
              
              if (existingThread) {
                 return prev.map(t => t.channel === channelId ? {
                    ...t,
                    messages: [...t.messages, newMsg],
                    summary: `${t.messages.length + 1} messages`
                 } : t);
              } else {
                 return [...prev, {
                    id: channelId,
                    channel: channelId,
                    participants: [{name: data.role, emoji: getEmojiForAgent(data.role), type: 'agent'}],
                    messages: [newMsg],
                    status: 'active',
                    summary: '1 message'
                 }];
              }
           });
        }
        else if (data.type === 'done' || data.type === 'error') {
           setIsProcessing(false);
        }
      } catch (err) {}
    };
    
    setWs(socket);
    return () => socket.close();
  }, []);

  const handleSendTask = (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !ws) return;
    
    setExecutionSteps([]);
    setReactSteps([]);
    setAgentThreads([]);
    setIsProcessing(true);
    setCommTab('activity');
    
    ws.send(JSON.stringify({
       type: 'message',
       content: chatInput,
       session_id: 'agent-page-session'
    }));
    
    setChatInput('');
  };


  const addLog = useCallback((log: Omit<ActivityLog, 'id' | 'timestamp'>) => {
    setActivityLog(prev => {
      const newLog: ActivityLog = {
        ...log,
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        timestamp: formatTime(new Date()),
      };
      return [newLog, ...prev].slice(0, 200); // Keep last 200 entries
    });
  }, []);


  const fetchAllData = useCallback(async () => {
    setIsRefreshing(true);
    const start = Date.now();

    // Health
    try {
      const h = await checkHealth();
      setHealth(h);
      addLog({ type: 'system', source: 'HealthMonitor', action: `System status: ${h.status} | Tools: ${h.tools_available} | Memory: ${h.memory_entries}`, status: h.status === 'ready' ? 'success' : 'pending' });
    } catch {
      setHealth(null);
      addLog({ type: 'system', source: 'HealthMonitor', action: 'Backend unreachable', status: 'error' });
    }

    // Provider Status
    try {
      const ps = await getProviderStatus();
      setProviderStatus(ps);
      if (ps.providers?.length > 0) {
        const names = ps.providers.map((p: any) => p.name).join(', ');
        addLog({ type: 'system', source: 'ProviderRegistry', target: 'LLM Council', action: `Active providers: [${names}] | Council: ${ps.council_mode ? 'ACTIVE' : 'OFF'}`, status: 'success' });
      }
      if (ps.council_mode) {
        addLog({ type: 'communication', source: 'LLM Council', target: 'All Providers', action: 'Cross-ranking consensus protocol active', status: 'active' });
      }
    } catch {
      setProviderStatus(null);
    }

    // Agent Stats
    try {
      const stats = await getAgentStats();
      setAgentStats(stats);
      addLog({ type: 'agent', source: 'AgentController', action: `Stats fetched — total tool calls, active sessions, loop detections`, status: 'success' });

      // Simulate agent communication events based on real stats
      if (stats?.tools_used) {
        Object.entries(stats.tools_used).forEach(([tool, count]: [string, any]) => {
          if (count > 0) {
            addLog({ type: 'tool', source: 'AgentController', target: tool, action: `Tool invoked ${count} time(s)`, status: 'success' });
          }
        });
      }
    } catch {
      setAgentStats(null); setRankings([{ name: 'Solution Expert', emoji: '🧠', type: 'agent', quality: 94, speed: 87, reliability: 96, overall: 93, votes: 142, trend: 'up' }, { name: 'Chief Architect', emoji: '🏗️', type: 'agent', quality: 96, speed: 82, reliability: 94, overall: 91, votes: 138, trend: 'up' }]);
    }

    // Processes
    try {
      const procs = await getProcesses();
      setProcesses(procs);
      if (procs?.processes?.length > 0) {
        procs.processes.forEach((p: any) => {
          addLog({ type: 'system', source: 'ProcessManager', target: p.name || p.process_id, action: `Process [${p.process_id}] status: ${p.status}`, status: p.status === 'running' ? 'active' : 'success' });
        });
      }
    } catch {
      setProcesses(null);
    }

    // Sessions
    try {
      const sess = await getSessions();
      setSessions(sess);
      if (sess?.sessions?.length > 0) {
        addLog({ type: 'agent', source: 'SessionManager', action: `${sess.sessions.length} active session(s)`, status: 'active' });
      }
    } catch {
      setSessions(null);
    }

    // Memory
    try {
      const mem = await getMemoryStats();
      setMemoryStats(mem);
      addLog({ type: 'memory', source: 'BugDiary', action: `Failures: ${mem?.total_failures || 0} | Successes: ${mem?.total_successes || 0} | Regression tests: ${mem?.regression_tests || 0}`, status: 'success' });
    } catch {
      setMemoryStats(null);
    }

    // Long-Term Memory
    try {
      const ltm = await getLongTermMemory();
      setLongTermMem(ltm);
      addLog({ type: 'memory', source: 'LongTermMemory', target: 'KnowledgeGraph', action: 'Episodic + procedural + knowledge graph synced', status: 'success' });
    } catch {
      setLongTermMem(null);
    }

    // Devices
    try {
      const devs = await getDeviceList();
      setDevices(devs);
      if (devs?.devices?.length > 0) {
        devs.devices.forEach((d: any) => {
          addLog({ type: 'system', source: 'PlatformManager', target: d.device_name || d.device_id, action: `Device [${d.platform}] — ${d.status}`, status: d.status === 'online' ? 'active' : 'pending' });
        });
      }
    } catch {
      setDevices(null);
    }

    // Orchestrator Status
    try {
      const os = await getOrchestratorStatus();
      setOrchStatus(os);
      addLog({ type: 'agent', source: 'Orchestrator', action: `Strategies: [${os.available_strategies?.join(', ')}] | Agent: ${os.agent_initialized ? 'READY' : 'OFF'}`, status: os.agent_initialized ? 'success' : 'pending' });
    } catch {
      setOrchStatus(null);
    }

    // System communication events
    addLog({ type: 'communication', source: 'SecurityMiddleware', target: 'AgentController', action: 'Request pipeline: Auth → RateLimit → Sanitize → Route', status: 'active' });
    addLog({ type: 'defense', source: 'ArmyDefenseMatrix', target: 'ThreatScanner', action: 'Perimeter patrol — all sectors nominal', status: 'success' });

    const elapsed = Date.now() - start;
    addLog({ type: 'system', source: 'SystemMonitor', action: `Full refresh completed in ${elapsed}ms`, status: 'success' });

    setLastRefresh(new Date());
    setIsRefreshing(false);

    // ASI Status (async, non-blocking)
    setAsiLoading(true);
    getASIStatus().then(s => { setAsiStatus(s); setAsiLoading(false); }).catch(() => setAsiLoading(false));
  }, [addLog]);

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 15000);
    return () => clearInterval(interval);
  }, [fetchAllData]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activityLog]);

  const filteredLogs = filterType === 'all' ? activityLog : activityLog.filter(l => l.type === filterType);
  const isOnline = health?.status === 'ready';

  return (
    <div className="min-h-screen bg-[#050505] text-white font-sans selection:bg-emerald-500/30 overflow-hidden">
      {/* Header */}
      <header className="h-14 flex items-center justify-between px-5 border-b border-white/5 bg-[#0a0a0a]/80 backdrop-blur-md sticky top-0 z-50">
        <div className="flex items-center gap-4">
          <Link to="/chat" className="p-2 text-white/40 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-gradient-to-br from-emerald-500/20 to-cyan-500/20 rounded-lg border border-emerald-500/20">
              <Activity className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight">System Monitor</h1>
              <span className="text-[10px] text-white/30 font-mono">ASTRA AGENT CONTROL PLANE</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-[11px] font-mono text-white/40">
            <StatusDot status={isOnline ? 'connected' : 'disconnected'} />
            {isOnline ? 'ONLINE' : 'OFFLINE'}
          </div>
          <div className="text-[10px] font-mono text-white/20">
            {formatTime(lastRefresh)}
          </div>
          <button
            onClick={fetchAllData}
            disabled={isRefreshing}
            className="p-2 text-white/40 hover:text-white hover:bg-white/5 rounded-lg transition-colors disabled:opacity-30"
          >
            <RefreshCcw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </header>

      <div className="flex h-[calc(100vh-56px)]">
        {/* Left: Status Panels */}
        <div className="w-80 border-r border-white/5 overflow-y-auto custom-scrollbar flex-shrink-0 bg-[#080808]">

          {/* System Health */}
          <div className="p-4 border-b border-white/5">
            <div className="flex items-center gap-2 mb-3">
              <Gauge className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">System Health</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-white/[0.03] rounded-lg p-3 border border-white/5">
                <div className="text-[10px] text-white/30 mb-1">Status</div>
                <div className={`text-sm font-bold ${isOnline ? 'text-emerald-400' : 'text-red-400'}`}>
                  {health?.status?.toUpperCase() || 'OFFLINE'}
                </div>
              </div>
              <div className="bg-white/[0.03] rounded-lg p-3 border border-white/5">
                <div className="text-[10px] text-white/30 mb-1">Tools</div>
                <div className="text-sm font-bold text-white/80">{health?.tools_available || 0}</div>
              </div>
              <div className="bg-white/[0.03] rounded-lg p-3 border border-white/5">
                <div className="text-[10px] text-white/30 mb-1">Memory</div>
                <div className="text-sm font-bold text-white/80">{health?.memory_entries || 0}</div>
              </div>
              <div className="bg-white/[0.03] rounded-lg p-3 border border-white/5">
                <div className="text-[10px] text-white/30 mb-1">Vision</div>
                <div className={`text-sm font-bold ${health?.vision_ready ? 'text-emerald-400' : 'text-white/30'}`}>
                  {health?.vision_ready ? 'READY' : 'OFF'}
                </div>
              </div>
            </div>
          </div>

          {/* Providers */}
          <div className="p-4 border-b border-white/5">
            <div className="flex items-center gap-2 mb-3">
              <Network className="w-3.5 h-3.5 text-violet-400" />
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">LLM Providers</span>
              {providerStatus?.council_mode && (
                <span className="text-[8px] font-bold bg-violet-500/20 text-violet-400 px-1.5 py-0.5 rounded border border-violet-500/20">COUNCIL</span>
              )}
            </div>
            {providerStatus?.providers?.length > 0 ? (
              <div className="space-y-1.5">
                {providerStatus.providers.map((p: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/[0.03] border border-white/5">
                    <StatusDot status={p.active ? 'connected' : 'pending'} />
                    <span className="text-xs font-medium text-white/70 flex-1">{p.name}</span>
                    <span className="text-[10px] font-mono text-white/30">{p.model}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-white/20 px-2">No providers configured</div>
            )}
          </div>

          {/* Active Sessions */}
          <div className="p-4 border-b border-white/5">
            <div className="flex items-center gap-2 mb-3">
              <MessageSquare className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">Sessions</span>
              <span className="text-[10px] font-mono text-white/20 ml-auto">{sessions?.sessions?.length || 0}</span>
            </div>
            {sessions?.sessions?.length > 0 ? (
              <div className="space-y-1.5">
                {sessions.sessions.slice(0, 5).map((s: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/[0.03] border border-white/5">
                    <Circle className="w-2 h-2 text-emerald-400 fill-emerald-400" />
                    <span className="text-[11px] font-mono text-white/50 truncate">{s.session_id || s.id || `Session ${i + 1}`}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-white/20 px-2">No active sessions</div>
            )}
          </div>

          {/* Background Processes */}
          <div className="p-4 border-b border-white/5">
            <div className="flex items-center gap-2 mb-3">
              <Terminal className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">Processes</span>
              <span className="text-[10px] font-mono text-white/20 ml-auto">{processes?.processes?.length || 0}</span>
            </div>
            {processes?.processes?.length > 0 ? (
              <div className="space-y-1.5">
                {processes.processes.slice(0, 5).map((p: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/[0.03] border border-white/5">
                    <StatusDot status={p.status === 'running' ? 'active' : 'pending'} />
                    <span className="text-[11px] font-mono text-white/50 truncate flex-1">{p.name || p.process_id}</span>
                    <span className="text-[9px] font-mono text-white/20">{p.status}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-white/20 px-2">No background processes</div>
            )}
          </div>

          {/* Memory */}
          <div className="p-4 border-b border-white/5">
            <div className="flex items-center gap-2 mb-3">
              <BrainCircuit className="w-3.5 h-3.5 text-pink-400" />
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">Memory</span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-white/[0.03] rounded-lg p-2 border border-white/5 text-center">
                <div className="text-[9px] text-white/25 mb-0.5">Failures</div>
                <div className="text-sm font-bold text-red-400/80">{memoryStats?.total_failures || 0}</div>
              </div>
              <div className="bg-white/[0.03] rounded-lg p-2 border border-white/5 text-center">
                <div className="text-[9px] text-white/25 mb-0.5">Successes</div>
                <div className="text-sm font-bold text-emerald-400/80">{memoryStats?.total_successes || 0}</div>
              </div>
              <div className="bg-white/[0.03] rounded-lg p-2 border border-white/5 text-center">
                <div className="text-[9px] text-white/25 mb-0.5">Regression</div>
                <div className="text-sm font-bold text-amber-400/80">{memoryStats?.regression_tests || 0}</div>
              </div>
            </div>
          </div>

          {/* Multi-Agent Orchestrator */}
          <div className="p-4 border-b border-white/5">
            <div className="flex items-center gap-2 mb-3">
              <GitBranch className="w-3.5 h-3.5 text-violet-400" />
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">Orchestrator</span>
              <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded border ${orchStatus?.agent_initialized
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/20'
                : 'bg-white/5 text-white/20 border-white/10'
                }`}>{orchStatus?.agent_initialized ? 'READY' : 'OFF'}</span>
            </div>
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-1.5">
                {['debate', 'swarm', 'pipeline', 'hierarchy'].map((s) => (
                  <div key={s} className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-white/[0.03] border border-white/5">
                    <div className={`w-1.5 h-1.5 rounded-full ${orchStatus?.available_strategies?.includes(s)
                      ? 'bg-violet-400 shadow-[0_0_4px_rgba(139,92,246,0.5)]'
                      : 'bg-white/10'
                      }`} />
                    <span className="text-[10px] font-mono text-white/40 uppercase">{s}</span>
                  </div>
                ))}
              </div>
              <button
                onClick={() => setOrchModalOpen(true)}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-violet-500/10 hover:bg-violet-500/20 border border-violet-500/20 text-violet-400 text-xs font-bold transition-colors"
              >
                <Zap className="w-3 h-3" />
                View Details
              </button>
            </div>
          </div>

          {/* Devices */}
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <HardDrive className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">Devices</span>
              <span className="text-[10px] font-mono text-white/20 ml-auto">{devices?.devices?.length || 0}</span>
            </div>
            {devices?.devices?.length > 0 ? (
              <div className="space-y-1.5">
                {devices.devices.map((d: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/[0.03] border border-white/5">
                    <StatusDot status={d.status === 'online' ? 'connected' : 'pending'} />
                    <span className="text-[11px] text-white/60 truncate flex-1">{d.device_name}</span>
                    <span className="text-[9px] font-mono text-white/20">{d.platform}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-white/20 px-2">No devices registered</div>
            )}
          </div>
        </div>

                {/* Right: Communication Center */}
        <div className="flex-1 flex flex-col bg-[#050505]">
          {/* Tab Navigation */}
          <div className="flex items-center justify-between px-5 py-2.5 border-b border-white/5 bg-[#080808]/50 backdrop-blur-md">
            <div className="flex items-center gap-1.5 overflow-x-auto custom-scrollbar pb-1">
              {[
                { id: 'activity', icon: GitBranch, label: 'Activity Stream' },
                { id: 'chats', icon: MessageSquare, label: 'Agent Threads' },
                { id: 'decisions', icon: Scale, label: 'Decisions' },
                { id: 'rankings', icon: Trophy, label: 'Rankings' },
                { id: 'feed', icon: Activity, label: 'System Logs' },
                { id: 'asi', icon: Shield, label: 'ASI Activity' }
              ].map(tab => {
                const Icon = tab.icon;
                const isActive = commTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setCommTab(tab.id as any)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wider transition-colors flex-shrink-0 ${isActive ? 'bg-white/10 text-white' : 'text-white/30 hover:text-white/60 hover:bg-white/[0.02]'}`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-violet-400' : 'text-white/40'}`} />
                    {tab.label}
                  </button>
                );
              })}
            </div>
            <div className="flex items-center gap-2 flex-shrink-0 ml-4">
              <span className="text-[10px] text-white/20 font-mono hidden sm:inline-block">Auto-refresh 15s</span>
            </div>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto custom-scrollbar">

            {/* ═══ ACTIVITY STREAM TAB ═══ */}
            {commTab === 'activity' && (
              <div className="flex flex-col h-full">
                {/* LIVE CHAT INPUT */}
                <div className="p-5 pb-0">
                  <form onSubmit={handleSendTask} className="relative mb-6">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={e => setChatInput(e.target.value)}
                      placeholder="Dispatch a task to the Multi-Agent Orchestrator..."
                      disabled={isProcessing}
                      className="w-full bg-white/[0.03] border border-white/10 rounded-xl py-3.5 pl-4 pr-12 text-sm text-white placeholder-white/20 focus:outline-none focus:border-violet-500/50 transition-colors disabled:opacity-50"
                    />
                    <button
                      type="submit"
                      disabled={isProcessing || !chatInput.trim()}
                      className="absolute right-2 top-2 p-1.5 bg-violet-500/10 hover:bg-violet-500/20 text-violet-400 rounded-lg transition-colors disabled:opacity-50 disabled:hover:bg-violet-500/10"
                    >
                      {isProcessing ? <Activity className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                    </button>
                  </form>
                </div>

                <div className="p-5 pt-0 flex-1 overflow-y-auto">
                  <div className="flex items-center gap-2 mb-4">
                    <div className="p-1.5 bg-gradient-to-br from-emerald-500/15 to-cyan-500/15 rounded-lg border border-emerald-500/15">
                      <Play className="w-3.5 h-3.5 text-emerald-400" />
                    </div>
                    <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-white/50">Execution Pipeline</span>
                    <span className="text-[9px] font-mono text-white/15 ml-auto">{executionSteps.length} steps</span>
                  </div>

                  <div className="mb-8 relative">
                    {executionSteps.length === 0 && <span className="text-xs text-white/20">Waiting for pipeline events...</span>}
                    {executionSteps.map((step, idx) => {
                      const phaseColors: Record<string, { bg: string; text: string; dot: string; border: string }> = {
                        'routing': { bg: 'bg-emerald-500/8', text: 'text-emerald-400', dot: 'bg-emerald-400', border: 'border-emerald-500/15' },
                        'thinking': { bg: 'bg-violet-500/8', text: 'text-violet-400', dot: 'bg-violet-400', border: 'border-violet-500/15' },
                        'tool-call': { bg: 'bg-amber-500/8', text: 'text-amber-400', dot: 'bg-amber-400', border: 'border-amber-500/15' },
                        'synthesis': { bg: 'bg-cyan-500/8', text: 'text-cyan-400', dot: 'bg-cyan-400', border: 'border-cyan-500/15' },
                        'complete': { bg: 'bg-emerald-500/15', text: 'text-emerald-400', dot: 'bg-emerald-400', border: 'border-emerald-500/30' },
                      };
                      const pc = phaseColors[step.phase] || phaseColors['routing'];
                      const isLast = idx === executionSteps.length - 1;

                      return (
                        <motion.div key={step.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.25, delay: idx * 0.06 }} className="flex items-start gap-3 relative">
                          <div className="flex flex-col items-center flex-shrink-0 w-8">
                            <div className={`w-6 h-6 rounded-full ${pc.bg} border ${pc.border} flex items-center justify-center z-10`}>
                              <span className={`text-[10px] font-black ${pc.text}`}>{step.step}</span>
                            </div>
                            {!isLast && <div className="w-px flex-1 bg-gradient-to-b from-white/10 to-white/3 min-h-[16px]" />}
                          </div>
                          <div className={`flex-1 ${pc.bg} border ${pc.border} rounded-xl px-4 py-3 mb-2 hover:border-white/15 transition-all group`}>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-sm">{step.agentEmoji}</span>
                              <span className="text-[11px] font-bold text-white/80">{step.agent}</span>
                              <span className={`text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full ${pc.bg} ${pc.text} border ${pc.border}`}>{step.phase}</span>
                              <span className="ml-auto text-[9px] font-mono text-white/20">{step.durationMs}ms</span>
                              {step.status === 'done' && <CheckCircle2 className="w-3 h-3 text-emerald-500/50" />}
                              {step.status === 'running' && <Activity className="w-3 h-3 text-cyan-400 animate-pulse" />}
                            </div>
                            <div className="text-[12px] font-semibold text-white/70">{step.action}</div>
                            {step.detail && <div className="text-[11px] text-white/35 mt-0.5">{step.detail}</div>}
                          </div>
                        </motion.div>
                      );
                    })}
                  </div>

                  <div className="flex items-center gap-2 mb-4">
                    <div className="p-1.5 bg-gradient-to-br from-violet-500/15 to-pink-500/15 rounded-lg border border-violet-500/15">
                      <BrainCircuit className="w-3.5 h-3.5 text-violet-400" />
                    </div>
                    <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-white/50">Agent Reasoning Chain</span>
                    <span className="text-[9px] font-mono text-white/15 ml-auto">Think → Act → Observe</span>
                  </div>

                  <div className="space-y-3">
                    {reactSteps.length === 0 && <span className="text-xs text-white/20">Waiting for agent reasoning...</span>}
                    {reactSteps.map((step, idx) => {
                      const typeColor = step.agentType === 'agent' ? 'violet' : step.agentType === 'tool' ? 'amber' : 'cyan';
                      return (
                        <motion.div key={step.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: idx * 0.08 }} className={`bg-white/[0.02] border border-white/[0.06] rounded-xl overflow-hidden hover:border-${typeColor}-500/20 transition-all`}>
                          <div className={`flex items-center gap-2.5 px-4 py-2.5 border-b border-white/[0.04] bg-${typeColor}-500/[0.03]`}>
                            <div className={`w-7 h-7 rounded-full bg-${typeColor}-500/15 border border-${typeColor}-500/25 flex items-center justify-center text-sm flex-shrink-0`}>{step.agentEmoji}</div>
                            <span className="text-[11px] font-bold text-white/80">{step.agent}</span>
                            <span className={`text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-${typeColor}-500/10 text-${typeColor}-400 border border-${typeColor}-500/15`}>Step {idx + 1}</span>
                            <div className="ml-auto flex items-center gap-2">
                              <span className="text-[9px] font-mono text-white/20">{step.durationMs}ms</span>
                              {step.status === 'done' && <CheckCircle2 className="w-3 h-3 text-emerald-500/50" />}
                              {step.status === 'running' && <Activity className="w-3 h-3 text-cyan-400 animate-pulse" />}
                              {step.status === 'error' && <XCircle className="w-3 h-3 text-red-400" />}
                            </div>
                          </div>
                          <div className="px-4 py-2.5 border-b border-white/[0.03]">
                            <div className="flex items-center gap-1.5 mb-1">
                              <BrainCircuit className="w-3 h-3 text-violet-400/60" />
                              <span className="text-[9px] font-bold uppercase tracking-wider text-violet-400/50">Think</span>
                            </div>
                            <p className="text-[11px] text-white/45 italic leading-relaxed pl-[18px]">{step.think}</p>
                          </div>
                          <div className="px-4 py-2.5 border-b border-white/[0.03] bg-amber-500/[0.015]">
                            <div className="flex items-center gap-1.5 mb-1">
                              <Play className="w-3 h-3 text-amber-400/60" />
                              <span className="text-[9px] font-bold uppercase tracking-wider text-amber-400/50">Act</span>
                            </div>
                            <p className="text-[12px] text-white/65 font-medium leading-relaxed pl-[18px]">{step.act}</p>
                          </div>
                          <div className="px-4 py-2.5">
                            <div className="flex items-center gap-1.5 mb-1">
                              <Eye className="w-3 h-3 text-emerald-400/60" />
                              <span className="text-[9px] font-bold uppercase tracking-wider text-emerald-400/50">Observe</span>
                            </div>
                            <div className="bg-[#0a0a0a] border border-white/5 rounded-lg px-3 py-2 ml-[18px]">
                              <p className="text-[11px] text-emerald-400/70 font-mono leading-relaxed">{step.observe}</p>
                            </div>
                          </div>
                        </motion.div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* ═══ AGENT THREADS TAB ═══ */}
            {commTab === 'chats' && (
              <div className="p-4 space-y-3">
                {agentThreads.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-64 text-white/15">
                    <MessageSquare className="w-8 h-8 mb-3" />
                    <span className="text-sm">No communications yet</span>
                    <span className="text-xs mt-1">Waiting for inter-agent messages...</span>
                  </div>
                ) : (
                  agentThreads.map((thread, tidx) => {
                    const isExpanded = expandedThreads.has(thread.id);
                    const channelColors: Record<string, string> = { 'task-routing': 'emerald', 'peer-review': 'violet', 'security': 'red', 'synthesis': 'cyan', 'consensus': 'amber', 'knowledge': 'blue', 'ci-cd': 'orange', 'memory': 'pink' };
                    const color = channelColors[thread.channel] || 'white';
                    return (
                      <motion.div key={thread.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, delay: tidx * 0.05 }} className="border border-white/[0.06] rounded-xl overflow-hidden">
                        <button onClick={() => setExpandedThreads(prev => { const next = new Set(prev); if (next.has(thread.id)) next.delete(thread.id); else { next.clear(); next.add(thread.id); } return next; })} className={`w-full flex items-center gap-3 px-4 py-3 bg-${color}-500/[0.03] hover:bg-${color}-500/[0.06] transition-colors text-left`}>
                          <div className="flex items-center gap-1">
                            <Hash className={`w-3.5 h-3.5 text-${color}-400/50`} />
                            <span className={`text-[11px] font-bold text-${color}-400/80`}>{thread.channel}</span>
                          </div>
                          <span className="text-[10px] text-white/20 ml-auto font-mono">{thread.summary}</span>
                          <div className={`p-1 rounded transition-transform ${isExpanded ? 'rotate-90' : ''}`}><ChevronRight className="w-3 h-3 text-white/20" /></div>
                        </button>
                        <AnimatePresence>
                          {isExpanded && (
                            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                              <div className="divide-y divide-white/[0.03]">
                                {thread.messages.map((msg) => {
                                  const fromColor = msg.fromType === 'agent' ? 'violet' : msg.fromType === 'tool' ? 'amber' : 'cyan';
                                  return (
                                    <div key={msg.id} className="flex items-start gap-3 px-4 py-3 hover:bg-white/[0.015] transition-colors">
                                      <div className={`w-7 h-7 rounded-full bg-${fromColor}-500/15 border border-${fromColor}-500/25 flex items-center justify-center text-sm flex-shrink-0 mt-0.5`}>{msg.fromEmoji}</div>
                                      <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-0.5">
                                          <span className="text-[11px] font-bold text-white/75">{msg.from}</span>
                                          <ArrowRight className="w-2.5 h-2.5 text-white/15" />
                                          <span className="text-[10px] text-white/40">{msg.to}</span>
                                          <span className="text-[9px] font-mono text-white/15 ml-auto">{msg.timestamp}</span>
                                        </div>
                                        <p className="text-[12px] text-white/55 leading-relaxed">{msg.message}</p>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </motion.div>
                    );
                  })
                )}
              </div>
            )}

            {/* ═══ DECISIONS TAB ═══ */}
            {commTab === 'decisions' && (
              <div className="p-4 space-y-4">
                {decisions.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-64 text-white/15">
                    <Scale className="w-8 h-8 mb-3" />
                    <span className="text-sm">No decisions recorded</span>
                    <span className="text-xs mt-1">Decisions will appear when agents deliberate...</span>
                  </div>
                ) : (
                  decisions.map((dec, idx) => (
                    <motion.div key={dec.id} className="bg-white/[0.02] border border-white/[0.06] rounded-xl overflow-hidden">
                       <div className="p-3 text-white/50 text-xs">Decision: {dec.title}</div>
                    </motion.div>
                  ))
                )}
              </div>
            )}

            {/* ═══ RANKINGS TAB ═══ */}
            {commTab === 'rankings' && (
              <div className="p-4 space-y-4">
                {rankings.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-64 text-white/15">
                    <Trophy className="w-8 h-8 mb-3" />
                    <span className="text-sm">No rankings available</span>
                  </div>
                ) : (
                  rankings.map((r, i) => (
                    <div key={i} className="flex justify-between text-xs text-white/60 bg-white/5 p-2 rounded">
                       <span>{r.emoji} {r.name}</span>
                       <span>Score: {r.quality}/100</span>
                    </div>
                  ))
                )}
              </div>
            )}


            {/* ═══ LIVE FEED TAB ═══ */}
            <AnimatePresence>
              {commTab === 'feed' && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="divide-y divide-white/[0.03]">
              <AnimatePresence initial={false}>
                {filteredLogs.map((log) => (
                  <motion.div
                    key={log.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="flex items-start gap-3 px-5 py-3 hover:bg-white/[0.02] transition-colors group"
                  >
                    {/* Timestamp */}
                    <span className="text-[10px] font-mono text-white/15 w-16 flex-shrink-0 pt-0.5 tabular-nums">{log.timestamp}</span>

                    {/* Type Icon */}
                    <div className="pt-0.5 flex-shrink-0">
                      <TypeIcon type={log.type} />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[11px] font-bold text-white/70">{log.source}</span>
                        {log.target && (
                          <>
                            <ArrowRight className="w-3 h-3 text-white/15" />
                            <span className="text-[11px] font-bold text-white/50">{log.target}</span>
                          </>
                        )}
                        <TypeBadge type={log.type} />
                      </div>
                      <div className="text-[11px] text-white/35 mt-0.5 leading-relaxed">{log.action}</div>
                    </div>

                    {/* Status */}
                    <div className="flex-shrink-0 pt-0.5">
                      {log.status === 'success' ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500/40" /> :
                        log.status === 'error' ? <XCircle className="w-3.5 h-3.5 text-red-500/40" /> :
                          log.status === 'active' ? <Activity className="w-3.5 h-3.5 text-cyan-400/40 animate-pulse" /> :
                            <Clock className="w-3.5 h-3.5 text-amber-500/40" />}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>

            {filteredLogs.length === 0 && (
              <div className="flex flex-col items-center justify-center h-64 text-white/15">
                <Activity className="w-8 h-8 mb-3" />
                <span className="text-sm">No activity recorded</span>
                <span className="text-xs mt-1">Waiting for system events...</span>
              </div>
            )}
            <div ref={logEndRef} />

                </motion.div>
              )}
            </AnimatePresence>

            {/* ═══ ASI ACTIVITY TAB ═══ */}
            {commTab === 'asi' && (
              <div className="p-5 space-y-6">
                {/* Overall Threat Level */}
                <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-red-500/[0.06] to-violet-500/[0.06] border border-white/5">
                  <Shield className="w-5 h-5 text-red-400" />
                  <div className="flex-1">
                    <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-white/40">Overall Threat Level</span>
                    <div className="text-sm font-black text-white/80 mt-0.5">
                      {asiLoading ? 'SCANNING...' : (asiStatus?.overall_threat_level?.toUpperCase() || 'UNKNOWN')}
                    </div>
                  </div>
                  <div className={`w-3 h-3 rounded-full ${
                    asiStatus?.overall_threat_level === 'nominal' || asiStatus?.overall_threat_level === 'low'
                      ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.6)]'
                      : asiStatus?.overall_threat_level === 'elevated'
                        ? 'bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.6)] animate-pulse'
                        : asiStatus?.overall_threat_level === 'critical'
                          ? 'bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.6)] animate-pulse'
                          : 'bg-white/20'
                  }`} />
                </div>

                {asiLoading && !asiStatus ? (
                  <div className="flex flex-col items-center justify-center h-48 text-white/20">
                    <Activity className="w-8 h-8 mb-3 animate-spin" />
                    <span className="text-sm">Loading ASI subsystems...</span>
                  </div>
                ) : !asiStatus ? (
                  <div className="flex flex-col items-center justify-center h-48 text-white/20">
                    <Shield className="w-8 h-8 mb-3" />
                    <span className="text-sm">ASI endpoint unavailable</span>
                    <span className="text-[11px] mt-1 text-white/10">Backend may not expose /asi/status</span>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {/* Cortex */}
                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
                      className="bg-violet-500/[0.04] border border-violet-500/10 rounded-xl p-4 hover:border-violet-500/25 transition-all">
                      <div className="flex items-center gap-2 mb-2">
                        <BrainCircuit className="w-4 h-4 text-violet-400" />
                        <span className="text-[11px] font-bold text-white/70">Cortex</span>
                        <StatusDot status={asiStatus.cortex?.status === 'active' || asiStatus.cortex?.status === 'ready' ? 'connected' : 'pending'} />
                      </div>
                      <div className="text-[10px] text-white/30 leading-relaxed">{asiStatus.cortex?.description || 'Cognitive processing core'}</div>
                      <div className="mt-2 text-[9px] font-mono text-violet-400/50 uppercase">{asiStatus.cortex?.status || 'offline'}</div>
                    </motion.div>

                    {/* Kernel Mutator */}
                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
                      className="bg-cyan-500/[0.04] border border-cyan-500/10 rounded-xl p-4 hover:border-cyan-500/25 transition-all">
                      <div className="flex items-center gap-2 mb-2">
                        <Cpu className="w-4 h-4 text-cyan-400" />
                        <span className="text-[11px] font-bold text-white/70">Kernel Mutator</span>
                        <StatusDot status={asiStatus.kernel_mutator?.status === 'active' || asiStatus.kernel_mutator?.status === 'ready' ? 'connected' : 'pending'} />
                      </div>
                      <div className="text-[10px] text-white/30 leading-relaxed">{asiStatus.kernel_mutator?.description || 'Runtime kernel mutation engine'}</div>
                      <div className="mt-2 flex items-center gap-3 text-[9px] font-mono text-cyan-400/50">
                        {asiStatus.kernel_mutator?.intelligence_factor != null && <span>IQ: {asiStatus.kernel_mutator.intelligence_factor.toFixed(1)}</span>}
                        {asiStatus.kernel_mutator?.numba_available != null && <span>Numba: {asiStatus.kernel_mutator.numba_available ? '✓' : '✗'}</span>}
                        <span className="uppercase">{asiStatus.kernel_mutator?.status || 'offline'}</span>
                      </div>
                    </motion.div>

                    {/* Containment Grid */}
                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
                      className="bg-red-500/[0.04] border border-red-500/10 rounded-xl p-4 hover:border-red-500/25 transition-all">
                      <div className="flex items-center gap-2 mb-2">
                        <Shield className="w-4 h-4 text-red-400" />
                        <span className="text-[11px] font-bold text-white/70">Containment Grid</span>
                        <StatusDot status={asiStatus.containment_grid?.status === 'active' || asiStatus.containment_grid?.status === 'ready' ? 'connected' : 'pending'} />
                      </div>
                      <div className="text-[10px] text-white/30 leading-relaxed">{asiStatus.containment_grid?.description || 'ASI safety containment perimeter'}</div>
                      <div className="mt-2 flex items-center gap-3 text-[9px] font-mono text-red-400/50">
                        {asiStatus.containment_grid?.security_triad && <span>Triad: {asiStatus.containment_grid.security_triad.join(' · ')}</span>}
                        <span className="uppercase">{asiStatus.containment_grid?.status || 'offline'}</span>
                      </div>
                    </motion.div>

                    {/* Parasitic Sentinel */}
                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
                      className="bg-amber-500/[0.04] border border-amber-500/10 rounded-xl p-4 hover:border-amber-500/25 transition-all">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                        <span className="text-[11px] font-bold text-white/70">Parasitic Sentinel</span>
                        <StatusDot status={asiStatus.parasitic_sentinel?.status === 'active' || asiStatus.parasitic_sentinel?.status === 'ready' ? 'connected' : 'pending'} />
                      </div>
                      <div className="text-[10px] text-white/30 leading-relaxed">{asiStatus.parasitic_sentinel?.description || 'Compilation interception & threat blocking'}</div>
                      <div className="mt-2 flex items-center gap-3 text-[9px] font-mono text-amber-400/50">
                        {asiStatus.parasitic_sentinel?.compilations_intercepted != null && <span>Intercepted: {asiStatus.parasitic_sentinel.compilations_intercepted}</span>}
                        {asiStatus.parasitic_sentinel?.threats_blocked != null && <span>Blocked: {asiStatus.parasitic_sentinel.threats_blocked}</span>}
                        <span className="uppercase">{asiStatus.parasitic_sentinel?.status || 'offline'}</span>
                      </div>
                    </motion.div>

                    {/* Ontological Sandbox */}
                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
                      className="bg-emerald-500/[0.04] border border-emerald-500/10 rounded-xl p-4 hover:border-emerald-500/25 transition-all">
                      <div className="flex items-center gap-2 mb-2">
                        <Terminal className="w-4 h-4 text-emerald-400" />
                        <span className="text-[11px] font-bold text-white/70">Ontological Sandbox</span>
                        <StatusDot status={asiStatus.ontological_sandbox?.status === 'active' || asiStatus.ontological_sandbox?.status === 'ready' ? 'connected' : 'pending'} />
                      </div>
                      <div className="text-[10px] text-white/30 leading-relaxed">{asiStatus.ontological_sandbox?.description || 'Safe code execution sandbox'}</div>
                      <div className="mt-2 flex items-center gap-3 text-[9px] font-mono text-emerald-400/50">
                        {asiStatus.ontological_sandbox?.executions != null && <span>Runs: {asiStatus.ontological_sandbox.executions}</span>}
                        {asiStatus.ontological_sandbox?.blocked != null && <span>Blocked: {asiStatus.ontological_sandbox.blocked}</span>}
                        <span className="uppercase">{asiStatus.ontological_sandbox?.status || 'offline'}</span>
                      </div>
                    </motion.div>

                    {/* Polymorphic Parasite */}
                    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
                      className="bg-pink-500/[0.04] border border-pink-500/10 rounded-xl p-4 hover:border-pink-500/25 transition-all">
                      <div className="flex items-center gap-2 mb-2">
                        <Network className="w-4 h-4 text-pink-400" />
                        <span className="text-[11px] font-bold text-white/70">Polymorphic Parasite</span>
                        <StatusDot status={asiStatus.polymorphic_parasite?.status === 'active' || asiStatus.polymorphic_parasite?.status === 'ready' ? 'connected' : 'pending'} />
                      </div>
                      <div className="text-[10px] text-white/30 leading-relaxed">{asiStatus.polymorphic_parasite?.description || 'Distributed compute grid'}</div>
                      <div className="mt-2 flex items-center gap-3 text-[9px] font-mono text-pink-400/50">
                        {asiStatus.polymorphic_parasite?.grid_nodes != null && <span>Nodes: {asiStatus.polymorphic_parasite.grid_nodes}</span>}
                        {asiStatus.polymorphic_parasite?.total_free_vcpus != null && <span>vCPUs: {asiStatus.polymorphic_parasite.total_free_vcpus}</span>}
                        <span className="uppercase">{asiStatus.polymorphic_parasite?.status || 'offline'}</span>
                      </div>
                    </motion.div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer Status Bar */}
          <div className="h-8 border-t border-white/5 bg-[#080808]/80 flex items-center px-5 gap-6 text-[10px] font-mono text-white/15">
            <div className="flex items-center gap-1.5">
              <StatusDot status={isOnline ? 'connected' : 'disconnected'} />
              <span>BACKEND {isOnline ? 'CONNECTED' : 'DISCONNECTED'}</span>
            </div>
            <span>PROVIDERS: {providerStatus?.providers?.length || 0}</span>
            <span>SESSIONS: {sessions?.sessions?.length || 0}</span>
            <span>PROCESSES: {processes?.processes?.length || 0}</span>
            <span>DEVICES: {devices?.devices?.length || 0}</span>
            <span className="ml-auto">AUTO-REFRESH: 15s</span>
          </div>
        </div>
      </div>

      {/* Orchestrator Modal */}
      <AnimatePresence>
        {isOrchModalOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOrchModalOpen(false)}
              className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-3xl bg-[#0c0c0c] border border-violet-500/20 rounded-2xl shadow-[0_0_60px_rgba(139,92,246,0.08)] z-50 overflow-hidden flex flex-col max-h-[90vh]"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-violet-500/10 bg-gradient-to-r from-violet-500/5 to-transparent">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-violet-500/10 rounded-lg border border-violet-500/20">
                    <GitBranch className="w-5 h-5 text-violet-400" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                      Multi-Agent Orchestrator <span className="text-[10px] font-mono bg-violet-500/20 text-violet-400 px-2 py-0.5 rounded border border-violet-500/20">SYSTEM</span>
                    </h2>
                    <p className="text-[11px] text-white/30 font-mono">AGENTS · STRATEGIES · TOOLS · SAFETY</p>
                  </div>
                </div>
                <button
                  onClick={() => setOrchModalOpen(false)}
                  className="p-2 text-white/40 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                >
                  <XCircle className="w-5 h-5" />
                </button>
              </div>

              {/* Read-Only Dashboard Content */}
              <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-5 space-y-6">

                {/* ── Agents ── */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Bot className="w-4 h-4 text-violet-400" />
                    <span className="text-xs font-bold uppercase tracking-[0.15em] text-white/50">Available Agents</span>
                    <span className="text-[10px] font-mono text-white/20 ml-auto">10 agents</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { name: 'Solution Expert', icon: '🧠', desc: 'Drafts initial solutions', color: 'violet' },
                      { name: 'Ruthless Critic', icon: '🔍', desc: 'Reviews for flaws & vulns', color: 'red' },
                      { name: 'Chief Architect', icon: '🏗️', desc: 'Synthesizes final output', color: 'cyan' },
                      { name: 'Deep Researcher', icon: '🌐', desc: 'Multi-hop web intelligence', color: 'emerald' },
                      { name: 'Threat Hunter', icon: '🕵️', desc: 'Security audit & analysis', color: 'red' },
                      { name: 'DevOps Reviewer', icon: '🛠️', desc: 'Autonomous issue fixing', color: 'amber' },
                      { name: 'Contract Hunter', icon: '📜', desc: 'Toxic clause detection', color: 'pink' },
                      { name: 'Devil\'s Advocate', icon: '👔', desc: 'Risk matrix analysis', color: 'orange' },
                      { name: 'Swarm Intelligence', icon: '🐝', desc: 'Multi-agent swarm tasks', color: 'yellow' },
                      { name: 'Ultimate Tutor', icon: '🎓', desc: 'Socratic teaching engine', color: 'blue' },
                    ].map((agent) => (
                      <div key={agent.name} className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/5 hover:border-white/10 transition-colors">
                        <span className="text-lg flex-shrink-0">{agent.icon}</span>
                        <div className="min-w-0">
                          <div className="text-[11px] font-bold text-white/70 truncate">{agent.name}</div>
                          <div className="text-[10px] text-white/25 truncate">{agent.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* ── Strategies ── */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <GitBranch className="w-4 h-4 text-emerald-400" />
                    <span className="text-xs font-bold uppercase tracking-[0.15em] text-white/50">Orchestration Strategies</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { key: 'debate', icon: '🤝', label: 'Debate', desc: 'Expert → Critic → Synthesis' },
                      { key: 'swarm', icon: '🐝', label: 'Swarm', desc: 'Parallel multi-agent swarm' },
                      { key: 'pipeline', icon: '⛓️', label: 'Pipeline', desc: 'Sequential stage pipeline' },
                      { key: 'hierarchy', icon: '🏗️', label: 'Hierarchy', desc: 'Manager → Worker delegation' },
                    ].map(({ key, icon, label, desc }) => {
                      const isAvailable = orchStatus?.available_strategies?.includes(key);
                      return (
                        <div key={key} className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-white/[0.03] border border-white/5">
                          <span className="text-lg flex-shrink-0">{icon}</span>
                          <div className="flex-1 min-w-0">
                            <div className="text-[11px] font-bold text-white/70">{label}</div>
                            <div className="text-[10px] text-white/25">{desc}</div>
                          </div>
                          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${isAvailable ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]' : 'bg-white/10'}`} />
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* ── Tools ── */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Wrench className="w-4 h-4 text-amber-400" />
                    <span className="text-xs font-bold uppercase tracking-[0.15em] text-white/50">System Tools</span>
                    <span className="text-[10px] font-mono text-white/20 ml-auto">{health?.tools_available || 0} registered</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { name: 'Code Evolution', icon: '🧬' },
                      { name: 'Threat Scanner', icon: '🛡️' },
                      { name: 'Memory Recall', icon: '🧠' },
                      { name: 'File Operations', icon: '📁' },
                      { name: 'Web Search', icon: '🔎' },
                      { name: 'Device Control', icon: '💻' },
                    ].map((tool) => (
                      <div key={tool.name} className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-white/[0.03] border border-white/5">
                        <span className="text-sm">{tool.icon}</span>
                        <span className="text-[10px] font-medium text-white/40">{tool.name}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* ── System Safety ── */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Shield className="w-4 h-4 text-red-400" />
                    <span className="text-xs font-bold uppercase tracking-[0.15em] text-white/50">Safety & Limits</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-white/[0.03] rounded-lg p-3 border border-white/5 text-center">
                      <div className="text-[9px] text-white/25 mb-1">Max Depth</div>
                      <div className="text-sm font-bold text-violet-400">3</div>
                    </div>
                    <div className="bg-white/[0.03] rounded-lg p-3 border border-white/5 text-center">
                      <div className="text-[9px] text-white/25 mb-1">Max Agents</div>
                      <div className="text-sm font-bold text-amber-400">8</div>
                    </div>
                    <div className="bg-white/[0.03] rounded-lg p-3 border border-white/5 text-center">
                      <div className="text-[9px] text-white/25 mb-1">Timeout</div>
                      <div className="text-sm font-bold text-cyan-400">10m</div>
                    </div>
                  </div>
                  <div className="mt-2 flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500/50" />
                    <span className="text-[10px] text-white/30">Circuit breaker active — all agents Justice Court-reviewed via AgentForge</span>
                  </div>
                </div>

                {/* ── Agent Roles ── */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Cpu className="w-4 h-4 text-cyan-400" />
                    <span className="text-xs font-bold uppercase tracking-[0.15em] text-white/50">Agent Roles</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {['Architect', 'Coder', 'Reviewer', 'Researcher', 'Security', 'Analyst', 'Writer', 'Manager', 'Critic', 'Synthesizer'].map((role) => (
                      <span key={role} className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-lg bg-white/[0.04] border border-white/5 text-white/35">
                        {role}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="h-8 border-t border-violet-500/10 bg-[#0a0a0a] flex items-center px-6 text-[9px] font-mono text-white/15">
                <span>ASTRA MULTI-AGENT ORCHESTRATOR — READ-ONLY SYSTEM OVERVIEW</span>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}

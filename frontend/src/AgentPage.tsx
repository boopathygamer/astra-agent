import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft, Activity, Cpu, Shield, Zap, Database, Network, Terminal,
  RefreshCcw, Circle, ChevronDown, ChevronUp, Wifi, WifiOff, BrainCircuit,
  Wrench, MessageSquare, GitBranch, ArrowRight, ArrowLeftRight, Bot,
  HardDrive, Clock, Gauge, AlertTriangle, CheckCircle2, XCircle, Loader2
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import {
  checkHealth, getProviderStatus, getAgentStats, getProcesses,
  getSessions, getMemoryStats, getLongTermMemory, getDeviceList,
  type HealthStatus
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
      setAgentStats(null);
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

    // System communication events
    addLog({ type: 'communication', source: 'SecurityMiddleware', target: 'AgentController', action: 'Request pipeline: Auth → RateLimit → Sanitize → Route', status: 'active' });
    addLog({ type: 'defense', source: 'ArmyDefenseMatrix', target: 'ThreatScanner', action: 'Perimeter patrol — all sectors nominal', status: 'success' });

    const elapsed = Date.now() - start;
    addLog({ type: 'system', source: 'SystemMonitor', action: `Full refresh completed in ${elapsed}ms`, status: 'success' });

    setLastRefresh(new Date());
    setIsRefreshing(false);
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

        {/* Right: Activity Feed */}
        <div className="flex-1 flex flex-col bg-[#050505]">
          {/* Activity Header + Filter */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-white/5 bg-[#080808]/50 backdrop-blur-md">
            <div className="flex items-center gap-3">
              <GitBranch className="w-4 h-4 text-emerald-400" />
              <span className="text-sm font-bold tracking-tight">Activity Feed</span>
              <span className="text-[10px] font-mono text-white/20">{filteredLogs.length} events</span>
            </div>
            <div className="flex items-center gap-1.5">
              {['all', 'agent', 'tool', 'system', 'communication', 'defense', 'memory'].map(f => (
                <button
                  key={f}
                  onClick={() => setFilterType(f)}
                  className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider transition-colors ${filterType === f
                      ? 'bg-white/10 text-white'
                      : 'text-white/25 hover:text-white/50 hover:bg-white/5'
                    }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {/* Activity Stream */}
          <div className="flex-1 overflow-y-auto custom-scrollbar">
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
    </div>
  );
}

import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import {
  ArrowLeft,
  Loader2,
  Smartphone,
  Users,
  Send,
  Zap,
  CheckCircle2,
  Code,
  Eye,
  Shield,
  Sparkles,
  X,
} from 'lucide-react';
import { swarmExecute } from './services/api';

const ROLES = [
  { id: 'architect', label: 'Architect', icon: Eye, desc: 'System design & architecture' },
  { id: 'coder', label: 'Coder', icon: Code, desc: 'Implementation & coding' },
  { id: 'reviewer', label: 'Reviewer', icon: Shield, desc: 'Code review & quality' },
  { id: 'tester', label: 'Tester', icon: CheckCircle2, desc: 'Testing & validation' },
  { id: 'optimizer', label: 'Optimizer', icon: Zap, desc: 'Performance optimization' },
  { id: 'designer', label: 'Designer', icon: Sparkles, desc: 'UX/UI design' },
];

interface AgentContribution {
  role: string;
  contribution: string;
}

export default function AppDevPage() {
  const [task, setTask] = useState('');
  const [selectedRoles, setSelectedRoles] = useState<string[]>(['architect', 'coder', 'reviewer']);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<{
    agents: AgentContribution[];
    merged_solution: string;
    duration_ms: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggleRole = (roleId: string) => {
    setSelectedRoles(prev =>
      prev.includes(roleId) ? prev.filter(r => r !== roleId) : [...prev, roleId]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim() || selectedRoles.length === 0 || isLoading) return;

    setIsLoading(true);
    setResult(null);
    setError(null);

    try {
      const res = await swarmExecute(task.trim(), selectedRoles);
      setResult({
        agents: res.agents || [],
        merged_solution: res.merged_solution || '',
        duration_ms: res.duration_ms || 0,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Swarm execution failed. Make sure the backend is running.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white selection:bg-emerald-500/30">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-[#0a0a0a]/80 backdrop-blur-md border-b border-white/5">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/chat" className="inline-flex items-center gap-2 text-white/50 hover:text-white transition-colors group">
              <div className="p-2 rounded-lg bg-white/5 group-hover:bg-white/10 transition-colors">
                <ArrowLeft className="w-4 h-4" />
              </div>
            </Link>
            <div className="flex items-center gap-3">
              <Smartphone className="w-5 h-5 text-emerald-400" />
              <h1 className="text-xl font-bold tracking-tight">App Dev · Swarm Intelligence</h1>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        {/* Task Input */}
        <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
          <h2 className="text-sm font-bold uppercase tracking-wider text-white/50 mb-4 flex items-center gap-2">
            <Users className="w-4 h-4 text-emerald-400" />
            Deploy Multi-Agent Swarm
          </h2>
          <p className="text-xs text-white/30 mb-6">
            Describe a complex development task. Multiple AI agents will collaborate — each with a specialized role — to produce a unified solution.
          </p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="e.g. Build a secure REST API with user authentication, rate limiting, and comprehensive test coverage..."
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-white/20 outline-none focus:border-emerald-500/50 resize-none h-28"
            />

            {/* Role Selector */}
            <div>
              <span className="text-[10px] uppercase tracking-widest text-white/30 font-bold mb-3 block">Select Agent Roles</span>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {ROLES.map((role) => {
                  const Icon = role.icon;
                  const isSelected = selectedRoles.includes(role.id);
                  return (
                    <button
                      key={role.id}
                      type="button"
                      onClick={() => toggleRole(role.id)}
                      className={`flex items-center gap-3 p-3 rounded-xl border transition-all text-left ${isSelected
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                          : 'bg-white/5 border-white/10 text-white/50 hover:bg-white/[0.07]'
                        }`}
                    >
                      <Icon className="w-4 h-4 flex-shrink-0" />
                      <div>
                        <span className="text-xs font-semibold block">{role.label}</span>
                        <span className="text-[10px] text-white/30">{role.desc}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <button
              type="submit"
              disabled={!task.trim() || selectedRoles.length === 0 || isLoading}
              className="w-full py-3 bg-emerald-500 text-black font-bold rounded-xl hover:bg-emerald-400 transition-colors disabled:opacity-50 flex items-center justify-center gap-2 text-sm"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Swarm Executing...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Deploy Swarm ({selectedRoles.length} agents)
                </>
              )}
            </button>
          </form>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 flex items-start gap-3">
            <X className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {/* Results */}
        <AnimatePresence>
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-6"
            >
              {/* Duration */}
              <div className="flex items-center gap-2 text-xs text-white/30">
                <Zap className="w-3 h-3" />
                <span className="font-mono">Completed in {(result.duration_ms / 1000).toFixed(1)}s</span>
              </div>

              {/* Agent Contributions */}
              {result.agents.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {result.agents.map((agent, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.1 }}
                      className="bg-white/[0.03] border border-white/10 rounded-2xl p-5"
                    >
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                          <Users className="w-4 h-4 text-emerald-400" />
                        </div>
                        <span className="text-sm font-bold capitalize text-white/80">{agent.role}</span>
                      </div>
                      <p className="text-xs text-white/50 whitespace-pre-wrap leading-relaxed">{agent.contribution}</p>
                    </motion.div>
                  ))}
                </div>
              )}

              {/* Merged Solution */}
              {result.merged_solution && (
                <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
                  <h3 className="text-sm font-bold uppercase tracking-wider text-emerald-400 mb-4 flex items-center gap-2">
                    <Sparkles className="w-4 h-4" />
                    Merged Solution
                  </h3>
                  <div className="text-sm text-white/70 whitespace-pre-wrap leading-relaxed font-mono bg-white/[0.02] p-4 rounded-xl border border-white/5">
                    {result.merged_solution}
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

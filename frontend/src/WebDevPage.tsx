import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import {
  ArrowLeft,
  Loader2,
  Code,
  Send,
  Zap,
  Brain,
  ChevronDown,
  ChevronUp,
  Terminal,
  FileCode,
  X,
  Copy,
  Check,
} from 'lucide-react';
import { agentTask } from './services/api';

export default function WebDevPage() {
  const [task, setTask] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showThinking, setShowThinking] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    answer: string;
    confidence: number;
    mode: string;
    iterations: number;
    tools_used: { tool: string; result: string }[];
    thinking_trace: {
      iterations: number;
      final_confidence: number;
      mode: string;
      steps: { iteration: number; action: string; confidence: number }[];
    } | null;
    duration_ms: number;
  } | null>(null);

  const PROMPTS = [
    { label: 'Build a REST API', prompt: 'Build a production-ready REST API with Express.js including authentication, rate limiting, error handling, and OpenAPI documentation' },
    { label: 'Create React Component', prompt: 'Create a reusable React data table component with sorting, filtering, pagination, and CSV export' },
    { label: 'Database Schema', prompt: 'Design a PostgreSQL database schema for a multi-tenant SaaS application with user management, subscriptions, and audit logging' },
    { label: 'CI/CD Pipeline', prompt: 'Write a GitHub Actions CI/CD pipeline for a Node.js app with testing, linting, Docker build, and deployment to AWS ECS' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim() || isLoading) return;

    setIsLoading(true);
    setResult(null);
    setError(null);

    try {
      const res = await agentTask(task.trim(), true, 10);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Agent task failed. Make sure the backend is running.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = () => {
    if (result?.answer) {
      navigator.clipboard.writeText(result.answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
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
              <Code className="w-5 h-5 text-emerald-400" />
              <h1 className="text-xl font-bold tracking-tight">Web Dev · Code Agent</h1>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        {/* Task Input */}
        <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
          <h2 className="text-sm font-bold uppercase tracking-wider text-white/50 mb-4 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-400" />
            Agent Task
          </h2>
          <p className="text-xs text-white/30 mb-4">
            Submit any coding task. The AI agent uses the full thinking loop with tool calls, multi-hypothesis reasoning, and self-verification.
          </p>

          {/* Quick prompts */}
          <div className="flex flex-wrap gap-2 mb-4">
            {PROMPTS.map((p, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setTask(p.prompt)}
                className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-[11px] text-white/50 hover:bg-white/10 hover:text-white/70 transition-colors"
              >
                {p.label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="Describe what you want to build..."
              className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-white/20 outline-none focus:border-emerald-500/50 resize-none h-28"
            />

            <button
              type="submit"
              disabled={!task.trim() || isLoading}
              className="w-full py-3 bg-emerald-500 text-black font-bold rounded-xl hover:bg-emerald-400 transition-colors disabled:opacity-50 flex items-center justify-center gap-2 text-sm"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Agent Processing...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Execute Task
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

        {/* Result */}
        <AnimatePresence>
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              {/* Meta Bar */}
              <div className="flex items-center justify-between bg-white/[0.03] border border-white/10 rounded-xl px-4 py-3">
                <div className="flex items-center gap-4 text-xs text-white/40">
                  <span className="font-mono flex items-center gap-1">
                    <Brain className="w-3 h-3 text-emerald-400" />
                    {result.mode}
                  </span>
                  <span className="font-mono">{(result.confidence * 100).toFixed(0)}% conf</span>
                  <span className="font-mono">{result.iterations} iter</span>
                  <span className="font-mono">{(result.duration_ms / 1000).toFixed(1)}s</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleCopy}
                    className="p-1.5 text-white/30 hover:text-white transition-colors rounded-lg hover:bg-white/5"
                  >
                    {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Tools Used */}
              {result.tools_used.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  <span className="text-[10px] uppercase tracking-widest text-white/30 font-bold mr-1 self-center">Tools:</span>
                  {result.tools_used.map((t, i) => (
                    <span key={i} className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] rounded-full font-mono">
                      {typeof t === 'object' ? t.tool : t}
                    </span>
                  ))}
                </div>
              )}

              {/* Thinking Trace */}
              {result.thinking_trace && (
                <div className="bg-white/[0.02] border border-white/5 rounded-xl">
                  <button
                    onClick={() => setShowThinking(!showThinking)}
                    className="w-full flex items-center justify-between px-4 py-3 text-xs text-white/30 hover:text-white/50 transition-colors"
                  >
                    <span className="flex items-center gap-2 font-mono uppercase tracking-wider">
                      <Brain className="w-3 h-3" />
                      Thinking Trace ({result.thinking_trace.iterations} steps)
                    </span>
                    {showThinking ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                  <AnimatePresence>
                    {showThinking && (
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: 'auto' }}
                        exit={{ height: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="px-4 pb-4 space-y-2">
                          {result.thinking_trace.steps.map((step, i) => (
                            <div key={i} className="flex items-start gap-3 pl-3 border-l border-emerald-500/20">
                              <span className="text-[10px] font-mono text-emerald-500/50 w-6 flex-shrink-0">#{step.iteration}</span>
                              <span className="text-xs text-white/40">{step.action}</span>
                              <span className="text-[10px] font-mono text-white/20 ml-auto">{(step.confidence * 100).toFixed(0)}%</span>
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}

              {/* Answer */}
              <div className="bg-white/[0.03] border border-white/10 rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-4">
                  <FileCode className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-bold uppercase tracking-wider text-white/50">Result</h3>
                </div>
                <div className="text-sm text-white/80 whitespace-pre-wrap leading-relaxed font-mono bg-white/[0.02] p-4 rounded-xl border border-white/5 overflow-x-auto">
                  {result.answer}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

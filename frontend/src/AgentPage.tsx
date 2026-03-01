import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  ArrowLeft,
  Send,
  Loader2,
  Brain,
  Wrench,
  CheckCircle2,
  ChevronRight,
  Activity,
  Target,
  Shield,
  BarChart3,
  Clock,
  Sparkles,
} from 'lucide-react';
import { useAgentStore } from './store/useAgentStore';

// ── Main Component ───────────────────────────────

export default function AgentPage() {
  const activities = useAgentStore(state => state.activities);
  const clearActivities = useAgentStore(state => state.clearActivities);

  const activitiesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll activities
  useEffect(() => {
    activitiesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activities]);

  // No local submit logic here anymore


  // Helper to render Markdown safely in the activity feed
  const renderMarkdown = (content: string) => (
    <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-[#1a1a1a] prose-pre:border prose-pre:border-white/10 prose-p:leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            return !inline && match ? (
              <SyntaxHighlighter
                {...props}
                style={vscDarkPlus}
                language={match[1]}
                PreTag="div"
                className="rounded-lg !mt-2 !mb-2 text-xs"
              >
                {String(children).replace(/\n$/, '')}
              </SyntaxHighlighter>
            ) : (
              <code {...props} className={`${className} bg-white/10 rounded px-1.5 py-0.5 text-[#e5e5e5] text-xs font-mono`}>
                {children}
              </code>
            );
          },
          a: ({ node, ...props }: any) => <a {...props} className="text-emerald-400 hover:text-emerald-300 underline underline-offset-2" target="_blank" rel="noopener noreferrer" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );

  return (
    <div className="h-screen bg-[#0a0a0a] text-white flex flex-col font-sans">
      {/* Header */}
      <header className="flex-shrink-0 bg-[#0a0a0a]/95 backdrop-blur-md border-b border-white/5 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/chat" className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 transition-colors">
              <ArrowLeft className="w-5 h-5 text-white/70" />
            </Link>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight text-white/90">Agent Console</h1>
                <div className="w-2 h-2 rounded-full bg-emerald-500" />
              </div>
              <span className="text-xs text-white/40 font-mono uppercase tracking-wider">
                Autonomous Execution Environment
              </span>
            </div>
          </div>
          <button
            onClick={clearActivities}
            className="flex items-center gap-2 px-3 py-1.5 bg-white/5 hover:bg-red-500/10 border border-white/10 hover:border-red-500/20 rounded-lg text-white/50 hover:text-red-400 text-sm font-mono tracking-wide transition-colors"
          >
            Clear Console
          </button>
        </div>
      </header>

      {/* Main Content (Activity Feed) */}
      <div className="flex-1 overflow-y-auto px-6 py-8 custom-scrollbar">
        <div className="max-w-5xl mx-auto">

          {activities.length === 0 && (
            <div className="flex flex-col items-center justify-center mt-20 text-center">
              <div className="w-20 h-20 mb-6 bg-gradient-to-br from-emerald-500/20 to-blue-500/20 rounded-3xl flex items-center justify-center border border-white/5 shadow-2xl shadow-emerald-500/10">
                <Activity className="w-10 h-10 text-emerald-400/80" />
              </div>
              <h2 className="text-2xl font-bold text-white/90 mb-3 tracking-tight">System Initialization Complete</h2>
              <p className="text-base text-white/40 max-w-lg leading-relaxed">
                The agent console is active. Return to the Chat interface and submit tasks to monitor the autonomous execution plan, tool routing, and reasoning trace here.
              </p>

              <div className="mt-10 grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-3xl">
                {[
                  { icon: Brain, label: 'Deep Reasoning', desc: 'Multi-hypothesis generation' },
                  { icon: Wrench, label: 'Tool Mastery', desc: 'Secure environment access' },
                  { icon: Shield, label: 'Self-Correction', desc: 'Autonomous error recovery' },
                  { icon: Target, label: 'Goal Oriented', desc: 'Determistic task completion' },
                ].map(({ icon: Icon, label, desc }) => (
                  <div key={label} className="flex flex-col items-center p-4 bg-white/[0.02] rounded-2xl border border-white/5 transition-colors hover:bg-white/[0.04]">
                    <Icon className="w-6 h-6 text-emerald-400/60 mb-3" />
                    <span className="text-sm font-semibold text-white/70 mb-1">{label}</span>
                    <span className="text-xs text-white/30 text-center">{desc}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-6">
            <AnimatePresence initial={false}>
              {activities.map((item, index) => {
                const isLast = index === activities.length - 1;

                // Styling based on activity type
                let icon = <ChevronRight className="w-5 h-5 text-white/30" />;
                let bgClass = "bg-white/[0.02]";
                let borderClass = "border-white/5";

                if (item.type === 'thinking') {
                  icon = <Brain className="w-5 h-5 text-purple-400" />;
                  borderClass = "border-purple-500/20";
                } else if (item.type === 'tool') {
                  icon = <Wrench className="w-5 h-5 text-blue-400" />;
                  borderClass = "border-blue-500/20";
                } else if (item.type === 'result') {
                  icon = <CheckCircle2 className="w-5 h-5 text-emerald-400" />;
                  bgClass = "bg-emerald-500/5";
                  borderClass = "border-emerald-500/30";
                } else if (item.type === 'error') {
                  icon = <Shield className="w-5 h-5 text-red-400" />;
                  bgClass = "bg-red-500/5";
                  borderClass = "border-red-500/30";
                } else if (item.type === 'user') {
                  icon = <Target className="w-5 h-5 text-amber-400" />;
                  bgClass = "bg-amber-500/5";
                  borderClass = "border-amber-500/20";
                }

                return (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`relative rounded-2xl border ${bgClass} ${borderClass} overflow-hidden shadow-lg`}
                  >
                    {/* Header */}
                    <div className="flex items-center justify-between px-5 py-3 border-b border-white/5 bg-white/[0.02]">
                      <div className="flex items-center gap-3">
                        <div className="p-1.5 rounded-lg bg-white/5">
                          {icon}
                        </div>
                        <span className="text-sm font-bold tracking-wide text-white/80">
                          {item.label}
                        </span>
                      </div>
                      <span className="text-xs text-white/30 font-mono tracking-wider">
                        {item.timestamp.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </span>
                    </div>

                    {/* Content */}
                    <div className="px-5 py-4">
                      {item.type === 'result' ? (
                        <div className="text-[15px] leading-relaxed">
                          {renderMarkdown(item.detail)}
                        </div>
                      ) : (
                        <p className="text-sm text-white/60 leading-relaxed font-mono whitespace-pre-wrap break-words">
                          {item.detail}
                        </p>
                      )}

                      {/* Metadata row (specifically for results) */}
                      {item.metadata && (
                        <div className="mt-5 pt-4 border-t border-white/5 flex flex-wrap gap-3">
                          {item.metadata.confidence !== undefined && (
                            <div className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20">
                              <BarChart3 className="w-3.5 h-3.5 text-emerald-400" />
                              <span className="text-xs font-mono text-emerald-400">
                                Conf: {(item.metadata.confidence * 100).toFixed(0)}%
                              </span>
                            </div>
                          )}
                          {item.metadata.durationMs !== undefined && (
                            <div className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-white/5 border border-white/10">
                              <Clock className="w-3.5 h-3.5 text-white/50" />
                              <span className="text-xs font-mono text-white/50">
                                {(item.metadata.durationMs / 1000).toFixed(2)}s
                              </span>
                            </div>
                          )}
                          {item.metadata.mode && (
                            <div className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-blue-500/10 border border-blue-500/20">
                              <Sparkles className="w-3.5 h-3.5 text-blue-400" />
                              <span className="text-xs font-mono text-blue-400 tracking-wide uppercase">
                                {item.metadata.mode}
                              </span>
                            </div>
                          )}
                          {item.metadata.iterations !== undefined && (
                            <div className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-purple-500/10 border border-purple-500/20">
                              <Brain className="w-3.5 h-3.5 text-purple-400" />
                              <span className="text-xs font-mono text-purple-400">
                                Iter: {item.metadata.iterations}
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
            <div ref={activitiesEndRef} className="h-4" />
          </div>
        </div>
      </div>
    </div>
  );
}


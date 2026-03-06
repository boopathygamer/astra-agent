import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Send, Mic, Paperclip, Image as ImageIcon, Play, Code2, Smartphone, Download, Settings, Maximize2, RotateCcw, Upload } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import ProjectUploader from './ProjectUploader';

export default function AppDevPage() {
  const [input, setInput] = useState('');
  const [activeTab, setActiveTab] = useState<'preview' | 'code'>('preview');
  const [messages, setMessages] = useState([
    { text: "I'm ready to help you build your mobile app. What kind of app are we creating today?", isUser: false }
  ]);
  const [showUploader, setShowUploader] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    setMessages([...messages, { text: input, isUser: true }]);
    setInput('');
  };

  return (
    <div className="h-screen bg-[#0a0a0a] text-white flex flex-col overflow-hidden font-sans">
      {/* Top Navigation Bar */}
      <header className="h-14 border-b border-white/10 flex items-center justify-between px-4 bg-[#141414] shrink-0">
        <div className="flex items-center gap-4">
          <Link to="/chat" className="inline-flex items-center gap-2 text-white/50 hover:text-white transition-colors">
            <ArrowLeft className="w-4 h-4" />
            <span className="text-sm font-medium">Back</span>
          </Link>
          <div className="w-px h-4 bg-white/10" />
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-blue-500/20 flex items-center justify-center border border-blue-500/30">
              <Smartphone className="w-3.5 h-3.5 text-blue-400" />
            </div>
            <span className="font-semibold text-sm tracking-tight">App Studio</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button onClick={() => setShowUploader(true)} className="px-3 py-1.5 text-xs font-medium text-white/70 hover:text-white hover:bg-white/5 rounded-md transition-colors flex items-center gap-1.5">
            <Upload className="w-3.5 h-3.5" />
            Import
          </button>
          <button className="px-3 py-1.5 text-xs font-medium text-white/70 hover:text-white hover:bg-white/5 rounded-md transition-colors flex items-center gap-1.5">
            <Download className="w-3.5 h-3.5" />
            Export
          </button>
          <button className="px-3 py-1.5 text-xs font-medium bg-white text-black hover:bg-gray-200 rounded-md transition-colors flex items-center gap-1.5">
            <Play className="w-3.5 h-3.5" />
            Build & Run
          </button>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="flex-1 flex overflow-hidden">

        {/* Left Pane: Assistant Chat */}
        <div className="w-[400px] border-r border-white/10 flex flex-col bg-[#0f0f0f] shrink-0">
          <div className="h-12 border-b border-white/5 flex items-center px-4 shrink-0">
            <span className="text-xs font-semibold text-white/50 uppercase tracking-wider">AI Assistant</span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.isUser ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${msg.isUser
                    ? 'bg-[#2f2f2f] text-white border border-white/5'
                    : 'bg-transparent text-white/90'
                  }`}>
                  {!msg.isUser && (
                    <div className="flex items-center gap-2 mb-1">
                      <div className="w-5 h-5 rounded bg-emerald-500/20 flex items-center justify-center border border-emerald-500/30">
                        <Code2 className="w-3 h-3 text-emerald-400" />
                      </div>
                      <span className="text-xs font-medium text-emerald-400">App Builder</span>
                    </div>
                  )}
                  {msg.text}
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 shrink-0 border-t border-white/5 bg-[#141414]">
            <form onSubmit={handleSubmit} className="relative flex items-end bg-[#1a1a1a] border border-white/10 rounded-xl p-2 focus-within:border-white/20 transition-colors">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Describe your app..."
                className="flex-1 bg-transparent border-none outline-none px-2 py-1.5 text-white placeholder-white/30 text-sm resize-none min-h-[40px] max-h-[120px] custom-scrollbar"
                rows={1}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit(e);
                  }
                }}
              />
              <div className="flex items-center gap-1 pb-1 pr-1 shrink-0">
                <button type="button" className="p-1.5 text-white/40 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
                  <ImageIcon className="w-4 h-4" />
                </button>
                <button
                  type="submit"
                  className={`p-1.5 rounded-lg transition-colors ${input.trim() ? 'bg-white text-black' : 'bg-white/5 text-white/20'}`}
                  disabled={!input.trim()}
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* Right Pane: Workspace */}
        <div className="flex-1 flex flex-col bg-[#0a0a0a] min-w-0">
          {/* Workspace Tabs */}
          <div className="h-12 border-b border-white/10 flex items-center justify-between px-4 shrink-0 bg-[#141414]">
            <div className="flex items-center gap-1">
              <button
                onClick={() => setActiveTab('preview')}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors flex items-center gap-2 ${activeTab === 'preview' ? 'bg-white/10 text-white' : 'text-white/50 hover:text-white hover:bg-white/5'}`}
              >
                <Smartphone className="w-4 h-4" />
                Preview
              </button>
              <button
                onClick={() => setActiveTab('code')}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors flex items-center gap-2 ${activeTab === 'code' ? 'bg-white/10 text-white' : 'text-white/50 hover:text-white hover:bg-white/5'}`}
              >
                <Code2 className="w-4 h-4" />
                Code
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button className="p-1.5 text-white/40 hover:text-white hover:bg-white/5 rounded-md transition-colors">
                <RotateCcw className="w-4 h-4" />
              </button>
              <button className="p-1.5 text-white/40 hover:text-white hover:bg-white/5 rounded-md transition-colors">
                <Maximize2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Workspace Content */}
          <div className="flex-1 relative overflow-hidden bg-[#0a0a0a]">
            <AnimatePresence mode="wait">
              {activeTab === 'preview' ? (
                <motion.div
                  key="preview"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="absolute inset-0 flex items-center justify-center p-8"
                >
                  {/* Mobile Device Mockup */}
                  <div className="w-[320px] h-[650px] bg-black rounded-[3rem] border-[8px] border-[#2a2a2a] shadow-2xl relative overflow-hidden flex flex-col">
                    {/* Notch */}
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-6 bg-[#2a2a2a] rounded-b-2xl z-20 flex items-center justify-center gap-2">
                      <div className="w-12 h-1 rounded-full bg-black/50" />
                      <div className="w-2 h-2 rounded-full bg-blue-900/50 border border-blue-500/20" />
                    </div>

                    {/* App Content Area */}
                    <div className="flex-1 bg-white mt-6 rounded-t-3xl overflow-hidden flex flex-col">
                      <div className="h-14 bg-blue-600 flex items-center justify-center text-white font-semibold shadow-sm">
                        My App
                      </div>
                      <div className="flex-1 flex items-center justify-center bg-gray-50 text-gray-400 text-sm p-6 text-center">
                        Your app preview will appear here once generated.
                      </div>
                    </div>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="code"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="absolute inset-0 p-4 overflow-auto custom-scrollbar"
                >
                  <div className="font-mono text-sm leading-relaxed">
                    <div className="flex">
                      <div className="w-8 text-white/20 select-none text-right pr-4">1</div>
                      <div className="text-pink-400">import <span className="text-white">React</span> from <span className="text-green-300">'react'</span>;</div>
                    </div>
                    <div className="flex">
                      <div className="w-8 text-white/20 select-none text-right pr-4">2</div>
                      <div className="text-pink-400">import <span className="text-white">{'{ View, Text, StyleSheet }'}</span> from <span className="text-green-300">'react-native'</span>;</div>
                    </div>
                    <div className="flex">
                      <div className="w-8 text-white/20 select-none text-right pr-4">3</div>
                      <div></div>
                    </div>
                    <div className="flex">
                      <div className="w-8 text-white/20 select-none text-right pr-4">4</div>
                      <div className="text-blue-400">export default function <span className="text-yellow-200">App</span><span className="text-white">() {'{'}</span></div>
                    </div>
                    <div className="flex">
                      <div className="w-8 text-white/20 select-none text-right pr-4">5</div>
                      <div className="text-white pl-4"><span className="text-pink-400">return</span> (</div>
                    </div>
                    <div className="flex">
                      <div className="w-8 text-white/20 select-none text-right pr-4">6</div>
                      <div className="text-white pl-8">{'<View style={styles.container}>'}</div>
                    </div>
                    <div className="flex">
                      <div className="w-8 text-white/20 select-none text-right pr-4">7</div>
                      <div className="text-white pl-12">{'<Text>Welcome to your new app!</Text>'}</div>
                    </div>
                    <div className="flex">
                      <div className="w-8 text-white/20 select-none text-right pr-4">8</div>
                      <div className="text-white pl-8">{'</View>'}</div>
                    </div>
                    <div className="flex">
                      <div className="w-8 text-white/20 select-none text-right pr-4">9</div>
                      <div className="text-white pl-4">);</div>
                    </div>
                    <div className="flex">
                      <div className="w-8 text-white/20 select-none text-right pr-4">10</div>
                      <div className="text-white">{'}'}</div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* Upload Modal */}
      <ProjectUploader
        mode="app"
        isOpen={showUploader}
        onClose={() => setShowUploader(false)}
        onImport={(files, analysis) => {
          setMessages(prev => [...prev, {
            text: `📂 Imported project: ${analysis.summary}\n\nReady to continue development. What would you like to change?`,
            isUser: false
          }]);
        }}
      />
    </div>
  );
}

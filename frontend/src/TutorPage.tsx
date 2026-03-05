import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Send, Mic, Pencil, Paperclip, Image as ImageIcon, X, Check, Trash2, Download, MousePointer2, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { startTutor, respondTutor, type TutorStartResponse } from './api';

interface Point {
  x: number;
  y: number;
}

interface TutorMessage {
  text: string;
  isUser: boolean;
}

export default function TutorPage() {
  const [input, setInput] = useState('');
  const [isDrawingMode, setIsDrawingMode] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);
  const [selectedColor, setSelectedColor] = useState('#ef4444');
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const contextRef = useRef<CanvasRenderingContext2D | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const pointsRef = useRef<Point[]>([]);

  // ── Tutor State ──
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const colors = [
    { name: 'Red', value: '#ef4444', bg: 'bg-red-500' },
    { name: 'Blue', value: '#3b82f6', bg: 'bg-blue-500' },
    { name: 'Green', value: '#22c55e', bg: 'bg-green-500' },
    { name: 'Purple', value: '#a855f7', bg: 'bg-purple-500' }
  ];

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

      const context = canvas.getContext('2d');
      if (context) {
        context.scale(dpr, dpr);
        context.lineCap = 'round';
        context.lineJoin = 'round';
        context.strokeStyle = selectedColor;
        context.lineWidth = 3;
        contextRef.current = context;
      }
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    return () => window.removeEventListener('resize', resizeCanvas);
  }, []);

  useEffect(() => {
    if (contextRef.current) {
      contextRef.current.strokeStyle = selectedColor;
    }
  }, [selectedColor]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const startDrawing = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isDrawingMode) return;

    const { x, y } = getCoordinates(e);
    setIsDrawing(true);
    pointsRef.current = [{ x, y }];

    contextRef.current?.beginPath();
    contextRef.current?.moveTo(x, y);
  };

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isDrawing || !isDrawingMode || !contextRef.current) return;

    const { x, y } = getCoordinates(e);
    const points = pointsRef.current;
    points.push({ x, y });

    if (points.length > 2) {
      const lastTwoPoints = points.slice(-3);
      const xc = (lastTwoPoints[1].x + lastTwoPoints[2].x) / 2;
      const yc = (lastTwoPoints[1].y + lastTwoPoints[2].y) / 2;

      contextRef.current.quadraticCurveTo(lastTwoPoints[1].x, lastTwoPoints[1].y, xc, yc);
      contextRef.current.stroke();
    }
  };

  const stopDrawing = () => {
    if (!isDrawing) return;
    setIsDrawing(false);
    pointsRef.current = [];
    contextRef.current?.closePath();
  };

  const getCoordinates = (e: React.MouseEvent | React.TouchEvent): Point => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };

    const rect = canvas.getBoundingClientRect();
    if ('nativeEvent' in e && e.nativeEvent instanceof MouseEvent) {
      return {
        x: e.nativeEvent.clientX - rect.left,
        y: e.nativeEvent.clientY - rect.top
      };
    } else {
      const touch = (e as React.TouchEvent).touches[0];
      return {
        x: touch.clientX - rect.left,
        y: touch.clientY - rect.top
      };
    }
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    const context = contextRef.current;
    if (canvas && context) {
      context.clearRect(0, 0, canvas.width, canvas.height);
    }
  };

  const downloadCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const link = document.createElement('a');
    link.download = 'sketch.png';
    link.href = canvas.toDataURL();
    link.click();
  };

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userText = input.trim();
    setMessages(prev => [...prev, { text: userText, isUser: true }]);
    setInput('');
    setIsLoading(true);

    try {
      if (!sessionId) {
        // Start a new tutor session
        const res = await startTutor(userText);
        setSessionId(res.session_id);
        setMessages(prev => [...prev, { text: res.greeting || res.response || JSON.stringify(res), isUser: false }]);
      } else {
        // Continue existing session
        const res = await respondTutor(sessionId, userText);
        setMessages(prev => [...prev, { text: res.response || JSON.stringify(res), isUser: false }]);
      }
    } catch (err: any) {
      setMessages(prev => [...prev, { text: `⚠️ ${err?.message || 'Failed to reach the tutor backend.'}`, isUser: false }]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, sessionId]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white p-6 overflow-hidden selection:bg-emerald-500/30">
      <header className="mb-8 flex items-center justify-between">
        <Link to="/chat" className="inline-flex items-center gap-2 text-white/50 hover:text-white transition-colors group">
          <div className="p-2 rounded-lg bg-white/5 group-hover:bg-white/10 transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </div>
          <span className="font-medium tracking-tight">Back to Chat</span>
        </Link>

        <div className="absolute left-1/2 -translate-x-1/2 flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
          <h1 className="text-xl font-bold tracking-tighter uppercase italic" style={{ fontFamily: 'var(--font-logo)' }}>
            Socratic Tutor
          </h1>
        </div>

        <div className="flex items-center gap-3">
          <AnimatePresence>
            {isDrawingMode && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="flex items-center gap-2 bg-white/5 p-1 rounded-xl border border-white/10 backdrop-blur-md"
              >
                <button
                  onClick={clearCanvas}
                  className="p-2 text-white/50 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all"
                  title="Clear Board"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
                <button
                  onClick={downloadCanvas}
                  className="p-2 text-white/50 hover:text-emerald-400 hover:bg-emerald-400/10 rounded-lg transition-all"
                  title="Download Sketch"
                >
                  <Download className="w-4 h-4" />
                </button>
                <div className="w-px h-4 bg-white/10 mx-1" />
                <button
                  onClick={() => setIsDrawingMode(false)}
                  className="flex items-center gap-2 px-3 py-1.5 text-xs font-semibold bg-white text-black rounded-lg hover:bg-gray-200 transition-colors"
                >
                  <MousePointer2 className="w-3 h-3" />
                  Exit Sketch
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </header>

      <div className="max-w-6xl mx-auto flex flex-col items-center justify-center h-[calc(100vh-160px)] relative">
        <div className="relative w-full h-full flex flex-col gap-6">

          {/* Main Board */}
          <div className="relative flex-1 bg-white rounded-2xl shadow-[0_0_100px_rgba(255,255,255,0.03)] border-[20px] border-[#f0f0f0] box-border overflow-hidden group transition-all duration-500">
            {/* Realistic Frame Details */}
            <div className="absolute inset-0 border-b-[6px] border-black/5 pointer-events-none z-20"></div>
            <div className="absolute inset-0 shadow-[inset_0_0_40px_rgba(0,0,0,0.05)] pointer-events-none z-20"></div>

            {/* Corners */}
            <div className="absolute -top-[20px] -left-[20px] w-14 h-14 bg-[#1a1a1a] rounded-tl-xl z-30 shadow-2xl flex items-center justify-center">
              <div className="w-2.5 h-2.5 rounded-full bg-white/10 animate-pulse"></div>
            </div>
            <div className="absolute -top-[20px] -right-[20px] w-14 h-14 bg-[#1a1a1a] rounded-tr-xl z-30 shadow-2xl flex items-center justify-center">
              <div className="w-2.5 h-2.5 rounded-full bg-white/10 animate-pulse"></div>
            </div>
            <div className="absolute -bottom-[20px] -left-[20px] w-14 h-14 bg-[#1a1a1a] rounded-bl-xl z-30 shadow-2xl flex items-center justify-center">
              <div className="w-2.5 h-2.5 rounded-full bg-white/10 animate-pulse"></div>
            </div>
            <div className="absolute -bottom-[20px] -right-[20px] w-14 h-14 bg-[#1a1a1a] rounded-br-xl z-30 shadow-2xl flex items-center justify-center">
              <div className="w-2.5 h-2.5 rounded-full bg-white/10 animate-pulse"></div>
            </div>

            {/* Board Surface */}
            <div className="w-full h-full bg-white relative">
              <div className="absolute inset-0 opacity-[0.02] pointer-events-none"
                style={{
                  backgroundImage: 'linear-gradient(#000 1px, transparent 1px), linear-gradient(90deg, #000 1px, transparent 1px)',
                  backgroundSize: '32px 32px'
                }}>
              </div>

              <canvas
                ref={canvasRef}
                onMouseDown={startDrawing}
                onMouseMove={draw}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
                onTouchStart={startDrawing}
                onTouchMove={draw}
                onTouchEnd={stopDrawing}
                className={`w-full h-full touch-none ${isDrawingMode ? 'cursor-crosshair' : 'cursor-default'}`}
              />

              <AnimatePresence>
                {!isDrawingMode && messages.length === 0 && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 flex items-center justify-center pointer-events-none select-none"
                  >
                    <div className="text-black/5 font-serif italic text-6xl tracking-tight rotate-[-4deg]">
                      Astra Sketchpad
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Tutor Messages Overlay */}
              {messages.length > 0 && !isDrawingMode && (
                <div className="absolute inset-0 overflow-y-auto p-6 space-y-4">
                  {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.isUser ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${msg.isUser
                          ? 'bg-emerald-500 text-black font-medium'
                          : 'bg-gray-100 text-gray-800 border border-gray-200'
                        }`}>
                        {msg.text}
                      </div>
                    </div>
                  ))}
                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="flex items-center gap-2 bg-gray-100 text-gray-500 rounded-2xl px-4 py-2.5 text-sm border border-gray-200">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Thinking...
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          </div>

          {/* Chat Input Bar */}
          <div className="relative mx-4">
            <AnimatePresence>
              {showColorPicker && (
                <motion.div
                  initial={{ opacity: 0, y: 20, scale: 0.9 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 20, scale: 0.9 }}
                  className="absolute bottom-full left-0 mb-6 bg-[#1a1a1a]/90 backdrop-blur-xl border border-white/10 rounded-3xl p-4 shadow-[0_20px_50px_rgba(0,0,0,0.5)] z-50 w-64"
                >
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[10px] font-bold text-white/30 uppercase tracking-[0.2em]">Select Ink Color</span>
                    <button onClick={() => setShowColorPicker(false)} className="p-1 hover:bg-white/5 rounded-full transition-colors">
                      <X className="w-3 h-3 text-white/40" />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    {colors.map((c) => (
                      <button
                        key={c.name}
                        onClick={() => {
                          setSelectedColor(c.value);
                          setIsDrawingMode(true);
                          setShowColorPicker(false);
                        }}
                        className={`flex items-center gap-3 p-3 rounded-2xl transition-all border ${selectedColor === c.value ? 'bg-white/10 border-white/20' : 'bg-white/5 border-transparent hover:bg-white/10'}`}
                      >
                        <div
                          className={`w-5 h-5 rounded-full shadow-inner ${c.bg} ring-2 ring-black/20`}
                        />
                        <span className="text-xs font-semibold text-white/80">{c.name}</span>
                        {selectedColor === c.value && (
                          <motion.div layoutId="active-color" className="ml-auto">
                            <Check className="w-3 h-3 text-emerald-400" />
                          </motion.div>
                        )}
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <form
              onSubmit={handleSubmit}
              className="h-14 bg-[#141414]/80 backdrop-blur-xl border border-white/10 rounded-xl shadow-[0_8px_32px_rgba(0,0,0,0.4)] flex items-center px-4 gap-4 focus-within:border-white/20 transition-all duration-300 relative group"
            >
              <div className="absolute inset-0 rounded-xl bg-gradient-to-b from-white/[0.02] to-transparent pointer-events-none" />

              <button
                type="button"
                onClick={() => setShowColorPicker(!showColorPicker)}
                className={`group relative p-2 transition-all rounded-lg ${isDrawingMode ? 'bg-emerald-500 text-black shadow-[0_0_15px_rgba(16,185,129,0.3)]' : 'text-white/40 hover:text-white hover:bg-white/5'}`}
              >
                <Pencil className="w-5 h-5" />
                {!isDrawingMode && (
                  <div className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-emerald-500 rounded-full border-2 border-[#141414] animate-pulse" />
                )}
              </button>

              <div className="flex-1">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={isDrawingMode ? "Sketching mode active..." : sessionId ? "Reply to the tutor..." : "Enter a topic to start learning..."}
                  className="w-full bg-transparent border-none outline-none text-white placeholder-white/20 text-sm font-medium"
                />
              </div>

              <div className="flex items-center gap-1.5">
                <button type="button" className="p-2 text-white/30 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
                  <ImageIcon className="w-4 h-4" />
                </button>
                <button type="button" className="p-2 text-white/30 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
                  <Paperclip className="w-4 h-4" />
                </button>
                <div className="w-px h-6 bg-white/10 mx-1"></div>
                <button type="button" className="p-2 text-white/30 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
                  <Mic className="w-4 h-4" />
                </button>
                <button
                  type="submit"
                  disabled={!input.trim() || isLoading}
                  className={`p-2 rounded-lg transition-all ${input.trim() && !isLoading ? 'bg-white text-black hover:scale-105 active:scale-95' : 'bg-white/5 text-white/20 cursor-not-allowed'}`}
                >
                  {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                </button>
              </div>
            </form>
          </div>

        </div>
      </div>
    </div>
  );
}

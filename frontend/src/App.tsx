/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getHealth } from './services/api';
import { motion, AnimatePresence, useScroll, useTransform } from 'motion/react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Cpu,
  Zap,
  Globe,
  ChevronRight,
  Bot,
  Code,
  ArrowRight,
  Menu,
  X,
  Terminal,
  Network,
  BrainCircuit,
  Layout,
  Shield,
  MessageSquare,
  GitBranch,
  Database
} from 'lucide-react';

// --- Components ---

const RobotBuilderCanvas = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    let time = 0;

    let isVisible = true;
    const observer = new IntersectionObserver((entries) => {
      isVisible = entries[0].isIntersecting;
    });
    observer.observe(canvas);

    let animationFrameId: number;

    // Background Grid
    const drawGrid = () => {
      ctx.strokeStyle = 'rgba(0, 255, 65, 0.05)';
      ctx.lineWidth = 1;
      const size = 50;
      const offsetX = (time * 10) % size;
      const offsetY = (time * 10) % size;

      ctx.beginPath();
      for (let x = -offsetX; x < width; x += size) {
        ctx.moveTo(x, 0); ctx.lineTo(x, height);
      }
      for (let y = -offsetY; y < height; y += size) {
        ctx.moveTo(0, y); ctx.lineTo(width, y);
      }
      ctx.stroke();
    };

    const render = () => {
      animationFrameId = requestAnimationFrame(render);
      if (!isVisible) return;

      time += 0.016;

      // Motion blur trail
      ctx.fillStyle = 'rgba(2, 2, 2, 0.3)';
      ctx.fillRect(0, 0, width, height);

      drawGrid();

      // Vignette
      const gradient = ctx.createRadialGradient(width / 2, height / 2, height / 3, width / 2, height / 2, height);
      gradient.addColorStop(0, 'transparent');
      gradient.addColorStop(1, 'rgba(0,0,0,0.8)');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);
    };

    render();

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return <canvas ref={canvasRef} className="absolute inset-0 z-0 pointer-events-none opacity-60 mix-blend-screen" />;
};

const CustomCursor = () => {
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const updatePos = (e: MouseEvent) => {
      setPos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', updatePos);
    return () => window.removeEventListener('mousemove', updatePos);
  }, []);

  return (
    <motion.div
      className="fixed top-0 left-0 w-8 h-8 rounded-full border-2 border-brand-primary pointer-events-none z-[100] mix-blend-screen hidden md:block"
      animate={{ x: pos.x - 16, y: pos.y - 16 }}
      transition={{ type: 'spring', stiffness: 500, damping: 28, mass: 0.5 }}
    >
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-1 bg-brand-primary rounded-full shadow-[0_0_10px_#00FF41]" />
    </motion.div>
  );
};

const CustomLogo = ({ className = "w-8 h-8" }: { className?: string }) => {
  const grid = [
    ".....1111.......",
    "....111111......",
    "....111111......",
    "....1111111.....",
    "....111111......",
    "....1...11......",
    "....11..11......",
    "....111111......",
    "....111111.11...",
    "....1111...11...",
    "....11111..1....",
    ".....111........",
    "......111.......",
    ".......111......",
    ".......11.......",
  ];

  return (
    <svg viewBox="0 0 16 15" className={`${className} drop-shadow-[0_0_12px_rgba(255,255,255,0.9)]`} fill="#FFFFFF" xmlns="http://www.w3.org/2000/svg">
      {grid.map((row, y) =>
        row.split('').map((cell, x) =>
          cell === '1' ? <rect key={`${x}-${y}`} x={x} y={y} width="1.05" height="1.05" /> : null
        )
      )}
    </svg>
  );
};

const Navbar = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [healthStatus, setHealthStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  useEffect(() => {
    let retryCount = 0;
    let timeoutId: ReturnType<typeof setTimeout>;

    const check = async () => {
      try {
        await getHealth();
        setHealthStatus('online');
        retryCount = 0;
        // Schedule next routine check after 10s once online
        timeoutId = setTimeout(check, 10000);
      } catch {
        retryCount++;
        // Stay in 'checking' state while retrying so the UI shows "Connecting..."
        setHealthStatus(retryCount >= 5 ? 'offline' : 'checking');
        // Exponential backoff: 2s, 4s, 8s, 16s … capped at 30s
        const delay = Math.min(2 ** retryCount * 1000, 30000);
        timeoutId = setTimeout(check, delay);
      }
    };

    check();
    return () => clearTimeout(timeoutId);
  }, []);

  return (
    <nav className="fixed top-0 left-0 w-full z-50">
      <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CustomLogo className="text-white w-8 h-8" />
          <span className="font-bold text-xl tracking-tighter lowercase" style={{ fontFamily: 'var(--font-logo)' }}>astra agent</span>
        </div>

        <div className="flex items-center gap-4">
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/10 bg-white/5">
            <div className={`w-2 h-2 rounded-full transition-colors ${healthStatus === 'online' ? 'bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.6)]' :
                healthStatus === 'offline' ? 'bg-red-500' : 'bg-yellow-500 animate-pulse'
              }`} />
            <span className="text-[10px] font-mono uppercase tracking-widest text-white/40">
              {healthStatus === 'online' ? 'Live' : healthStatus === 'offline' ? 'Offline' : 'Connecting...'}
            </span>
          </div>
          <button className="hidden sm:block text-sm font-medium px-4 py-2 border border-white/10 rounded-full hover:bg-white/5 transition-colors">
            Sign In
          </button>
          <Link to="/chat" className="bg-brand-primary text-black text-sm font-bold px-6 py-2 rounded-full hover:scale-105 transition-transform">
            Get Started
          </Link>
          <button className="md:hidden" onClick={() => setIsOpen(!isOpen)}>
            {isOpen ? <X /> : <Menu />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="md:hidden absolute top-20 left-0 w-full bg-black border-b border-white/10 p-6 flex flex-col gap-4"
          >
            <button className="text-sm font-medium px-4 py-3 border border-white/10 rounded-lg hover:bg-white/5 transition-colors text-left">
              Sign In
            </button>
            <Link to="/chat" className="bg-brand-primary text-black text-sm font-bold px-4 py-3 rounded-lg hover:scale-[1.02] transition-transform text-center">
              Get Started
            </Link>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
};



const StatBlock = ({ label, value }) => (
  <div className="text-center">
    <div className="text-4xl md:text-5xl font-mono font-bold tracking-tighter mb-2">{value}</div>
    <div className="text-xs uppercase tracking-widest text-white/40 font-semibold">{label}</div>
  </div>
);



const AdvancedHeading = () => {
  const text1 = "Engineered";
  const text2 = "For Scale";

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      whileInView={{ opacity: 1, scale: 1 }}
      transition={{ duration: 1.5, type: "spring", bounce: 0.3 }}
      viewport={{ once: false, margin: "-100px" }}
      className="relative inline-block perspective-1000"
    >
      {/* Background Glow */}
      <motion.div
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.2, 0.5, 0.2],
          rotateZ: [0, 5, 0, -5, 0]
        }}
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
        className="absolute inset-0 bg-brand-primary/40 blur-[40px] -z-10 rounded-full"
      />

      <h2 className="text-4xl sm:text-6xl md:text-8xl lg:text-9xl font-black tracking-tighter mb-6 uppercase relative z-10 leading-[0.85] flex flex-col items-center">
        {/* Top Line */}
        <div className="relative overflow-hidden pb-2">
          <motion.span
            initial={{ y: "100%" }}
            whileInView={{ y: 0 }}
            transition={{ duration: 0.8, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            className="text-transparent bg-clip-text bg-gradient-to-b from-white via-white to-white/20 block relative z-20"
          >
            {text1}
          </motion.span>
          <motion.div
            animate={{ x: ["-100%", "200%"] }}
            transition={{ duration: 3, repeat: Infinity, ease: "linear", delay: 1 }}
            className="absolute top-0 left-0 w-1/2 h-full bg-gradient-to-r from-transparent via-white/30 to-transparent -skew-x-12 z-30 mix-blend-overlay"
          />
        </div>

        {/* Bottom Line */}
        <div className="relative overflow-hidden">
          <motion.span
            initial={{ y: "-100%" }}
            whileInView={{ y: 0 }}
            transition={{ duration: 0.8, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="text-transparent bg-clip-text bg-gradient-to-b from-brand-primary via-brand-primary to-brand-primary/20 block relative z-20"
          >
            {text2}
          </motion.span>

          {/* Glitch Layers for Bottom Line */}
          <motion.span
            animate={{ x: [-3, 3, -3], y: [2, -2, 2], opacity: [0, 0.8, 0] }}
            transition={{ duration: 0.15, repeat: Infinity, repeatType: "reverse", repeatDelay: 2 }}
            className="absolute top-0 left-0 w-full h-full text-brand-primary mix-blend-screen blur-[2px] -z-10 block"
            aria-hidden="true"
          >
            {text2}
          </motion.span>
          <motion.span
            animate={{ x: [3, -3, 3], y: [-2, 2, -2], opacity: [0, 0.8, 0] }}
            transition={{ duration: 0.2, repeat: Infinity, repeatType: "reverse", repeatDelay: 2.1 }}
            className="absolute top-0 left-0 w-full h-full text-[#ff00ff] mix-blend-screen blur-[1px] -z-10 block"
            aria-hidden="true"
          >
            {text2}
          </motion.span>
        </div>
      </h2>

      {/* Decorative Lines */}
      <motion.div
        initial={{ scaleX: 0 }}
        whileInView={{ scaleX: 1 }}
        transition={{ duration: 1, delay: 0.5 }}
        className="absolute -left-12 top-1/2 w-8 h-px bg-brand-primary/50"
      />
      <motion.div
        initial={{ scaleX: 0 }}
        whileInView={{ scaleX: 1 }}
        transition={{ duration: 1, delay: 0.5 }}
        className="absolute -right-12 top-1/2 w-8 h-px bg-brand-primary/50"
      />
    </motion.div>
  );
};



const CyberButton = ({ text, onClick, className = "" }: { text: string, onClick?: () => void, className?: string }) => {
  return (
    <button onClick={onClick} className={`group relative inline-block focus:outline-none ${className}`}>
      <div className="relative z-10 inline-flex items-center justify-center px-12 py-4 font-mono font-black text-xl tracking-widest uppercase bg-[#00FF41] text-black border-4 border-black shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] hover:translate-y-1 hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-1 transition-all active:translate-y-2 active:translate-x-2 active:shadow-none rounded-full">
        {/* Pixel Highlight */}
        <div className="absolute top-0 left-0 w-full h-full pointer-events-none overflow-hidden rounded-full">
          <div className="absolute top-3 left-8 w-4 h-1 bg-white"></div>
          <div className="absolute top-3 left-8 w-1 h-3 bg-white"></div>
          <div className="absolute top-4 left-9 w-1 h-1 bg-white"></div>
        </div>

        <span className="mr-2 relative z-10">{text}</span>
        <ChevronRight className="w-6 h-6 stroke-[3] relative z-10" />
      </div>
    </button>
  );
};

const MindMap = () => {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const nodes = [
    { id: 'core', label: 'Astra Agent', x: 50, y: 50, mobileX: 50, mobileY: 50, type: 'main', icon: Bot, sub: 'System Core' },
    { id: 'cognitive', label: 'Cognitive Core', x: 20, y: 25, mobileX: 20, mobileY: 20, type: 'card', icon: BrainCircuit, sub: 'Processing' },
    { id: 'orchestration', label: 'Orchestration', x: 80, y: 25, mobileX: 80, mobileY: 20, type: 'card', icon: Network, sub: 'Routing' },
    { id: 'justice', label: 'Justice Defense', x: 20, y: 75, mobileX: 20, mobileY: 80, type: 'card', icon: Shield, sub: 'Security' },
    { id: 'agent', label: 'Core Agent', x: 80, y: 75, mobileX: 80, mobileY: 80, type: 'card', icon: Cpu, sub: 'Execution' },
    { id: 'tutor', label: 'Socratic Tutor', x: 50, y: 15, mobileX: 50, mobileY: 10, type: 'pill', icon: MessageSquare },
    { id: 'dev', label: 'App & Web Dev', x: 50, y: 85, mobileX: 50, mobileY: 90, type: 'pill', icon: Code },
  ];

  const connections = [
    { from: 'core', to: 'cognitive' },
    { from: 'core', to: 'orchestration' },
    { from: 'core', to: 'justice' },
    { from: 'core', to: 'agent' },
    { from: 'core', to: 'tutor' },
    { from: 'core', to: 'dev' },
  ];

  return (
    <div className="relative w-full max-w-6xl mx-auto h-[600px] md:h-[700px] lg:aspect-[16/9] lg:h-auto mt-12 md:mt-24 mb-0 bg-gradient-to-b from-white/5 to-transparent rounded-t-[3rem] rounded-b-none border-x border-t border-b-0 border-white/10 backdrop-blur-3xl overflow-hidden shadow-2xl">
      {/* Subtle Ambient Background */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-full bg-[radial-gradient(circle_at_50%_50%,rgba(0,255,65,0.05),transparent_70%)] pointer-events-none" />

      <svg className="absolute inset-0 w-full h-full pointer-events-none">
        {connections.map((conn, i) => {
          const fromNode = nodes.find(n => n.id === conn.from);
          const toNode = nodes.find(n => n.id === conn.to);
          if (!fromNode || !toNode) return null;

          const from = {
            x: isMobile ? fromNode.mobileX : fromNode.x,
            y: isMobile ? fromNode.mobileY : fromNode.y
          };
          const to = {
            x: isMobile ? toNode.mobileX : toNode.x,
            y: isMobile ? toNode.mobileY : toNode.y
          };

          // Calculate control points for smooth bezier curves
          const midX = (from.x + to.x) / 2;
          const midY = (from.y + to.y) / 2;
          const path = `M ${from.x}% ${from.y}% Q ${midX}% ${to.y}% ${to.x}% ${to.y}%`;

          return (
            <g key={i}>
              <motion.path
                d={path}
                fill="none"
                stroke="url(#gradient-line)"
                strokeWidth="1.5"
                initial={{ pathLength: 0, opacity: 0 }}
                whileInView={{ pathLength: 1, opacity: 0.4 }}
                transition={{ duration: 1.5, delay: 0.2 }}
              />
            </g>
          );
        })}
        <defs>
          <linearGradient id="gradient-line" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.1)" />
            <stop offset="50%" stopColor="rgba(0,255,65,0.4)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0.1)" />
          </linearGradient>
        </defs>
      </svg>

      {nodes.map((node) => {
        const Icon = node.icon;
        const isHovered = hoveredNode === node.id;
        const x = isMobile ? node.mobileX : node.x;
        const y = isMobile ? node.mobileY : node.y;

        return (
          <motion.div
            key={node.id}
            className="absolute transform -translate-x-1/2 -translate-y-1/2 z-10"
            style={{ left: `${x}%`, top: `${y}%` }}
            initial={{ scale: 0.9, opacity: 0, y: 20 }}
            whileInView={{ scale: 1, opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: node.type === 'main' ? 0 : 0.2 }}
            onMouseEnter={() => setHoveredNode(node.id)}
            onMouseLeave={() => setHoveredNode(null)}
          >
            {node.type === 'main' && (
              <div className="relative group cursor-pointer">
                <div className="absolute inset-0 bg-brand-primary/20 blur-[60px] rounded-full group-hover:bg-brand-primary/30 transition-all duration-700" />
                <div className="relative bg-white/10 border border-white/20 p-6 md:p-8 rounded-[2rem] backdrop-blur-xl shadow-2xl flex flex-col items-center gap-4 transition-transform duration-500 hover:scale-105 hover:border-brand-primary/30">
                  <div className="p-3 md:p-4 bg-gradient-to-br from-brand-primary to-emerald-600 rounded-2xl shadow-lg shadow-brand-primary/20">
                    <Icon className="w-8 h-8 md:w-10 md:h-10 text-black" />
                  </div>
                  <div className="text-center">
                    <h3 className="font-sans font-bold text-white text-lg md:text-2xl tracking-tight whitespace-nowrap">{node.label}</h3>
                    <p className="text-xs md:text-sm text-white/50 font-sans mt-1">{node.sub}</p>
                  </div>
                </div>
              </div>
            )}

            {node.type === 'card' && (
              <div className={`
                group cursor-pointer bg-white/5 border border-white/10 hover:border-white/20 hover:bg-white/10
                p-3 md:p-5 rounded-2xl flex items-center gap-3 md:gap-4 min-w-[160px] md:min-w-[220px] backdrop-blur-lg
                transition-all duration-300 hover:-translate-y-1 hover:shadow-xl
              `}>
                <div className={`p-2 md:p-3 rounded-xl bg-white/5 group-hover:bg-brand-primary/20 transition-colors duration-300`}>
                  <Icon size={16} className="text-white/70 group-hover:text-brand-primary transition-colors md:w-5 md:h-5" />
                </div>
                <div className="flex flex-col">
                  <span className="text-sm md:text-base font-semibold text-white tracking-tight whitespace-nowrap">{node.label}</span>
                  <span className="text-[10px] md:text-xs text-white/40 font-sans">{node.sub}</span>
                </div>
              </div>
            )}

            {node.type === 'pill' && (
              <div className={`
                group cursor-pointer bg-white/5 border border-white/10 hover:border-white/20 hover:bg-white/10
                px-4 py-2 md:px-6 md:py-3 rounded-full flex items-center gap-2 md:gap-3 backdrop-blur-lg
                transition-all duration-300 hover:scale-105 hover:shadow-lg
              `}>
                <Icon size={14} className="text-white/60 group-hover:text-brand-primary transition-colors md:w-4 md:h-4" />
                <span className="text-xs md:text-sm font-medium text-white/80 group-hover:text-white transition-colors whitespace-nowrap">{node.label}</span>
              </div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
};

export default function App() {
  const navigate = useNavigate();
  const { scrollYProgress } = useScroll();
  const opacity = useTransform(scrollYProgress, [0, 0.2], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.2], [1, 0.95]);

  return (
    <div className="min-h-screen selection:bg-brand-primary selection:text-black crt cursor-none">
      <CustomCursor />
      <Navbar />

      {/* Hero Section */}
      <section className="relative pt-24 pb-12 md:pt-32 md:pb-20 px-6 overflow-hidden min-h-screen flex items-center justify-center">
        <RobotBuilderCanvas />
        <motion.div
          style={{ opacity, scale }}
          className="max-w-7xl mx-auto text-center relative z-10 mt-12 md:mt-24"
        >
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-4xl sm:text-6xl md:text-8xl lg:text-[120px] font-black tracking-tighter leading-none md:leading-[0.9] mb-6 md:mb-8 glow-text uppercase relative"
          >
            <div className="glitch-wrapper">
              <div className="glitch" data-text="AUTONOMOUS AI">AUTONOMOUS AI</div>
            </div>
            <div className="glitch-wrapper mt-2">
              <div className="glitch text-brand-primary" data-text="SYSTEM">SYSTEM</div>
            </div>
          </motion.h1>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-6"
          >
            <CyberButton text="Get Start" onClick={() => navigate('/chat')} className="w-full sm:w-auto" />
          </motion.div>
        </motion.div>



        {/* Background Decoration */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-brand-primary/10 rounded-full blur-[150px] -z-10 mix-blend-screen pointer-events-none" />
      </section>

      {/* Stats Section */}
      <section className="py-10 md:py-20 border-y border-white/5 bg-brand-surface/30">
        <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-3 gap-6 md:gap-12">
          <StatBlock label="Active Agents" value="More" />
          <StatBlock label="Recursive Depth" value="∞" />
          <StatBlock label="Uptime" value="99.99%" />
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-16 md:py-32 px-6 relative">
        <div className="max-w-7xl mx-auto relative z-10">
          <div className="mb-16 md:mb-32 text-center sticky top-10 z-0 flex flex-col items-center justify-center min-h-[30vh] md:min-h-[40vh]">
            <AdvancedHeading />

            <MindMap />

            <motion.div
              initial={{ opacity: 0, y: -10 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="w-full max-w-6xl mx-auto bg-white/5 border-x border-b border-white/10 rounded-b-[3rem] p-8 md:p-12 backdrop-blur-md relative z-20"
            >
              <div className="flex flex-col md:flex-row items-center gap-6 md:gap-12">
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 rounded-full bg-brand-primary/10 flex items-center justify-center border border-brand-primary/20">
                    <Terminal className="text-brand-primary w-6 h-6" />
                  </div>
                </div>
                <p className="text-white/70 text-base md:text-xl font-light tracking-wide text-left leading-relaxed">
                  Our protocol handles the complexity of agent communication, state management, and recursive spawning so you can focus on the mission.
                </p>
              </div>
            </motion.div>
          </div>
        </div>

        {/* Background VFX */}
        <div className="absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute top-1/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-brand-primary/20 to-transparent" />
          <div className="absolute top-2/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-brand-primary/20 to-transparent" />
          <div className="absolute top-3/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-brand-primary/20 to-transparent" />
          <div className="absolute top-0 left-1/4 w-px h-full bg-gradient-to-b from-transparent via-brand-primary/10 to-transparent" />
          <div className="absolute top-0 left-3/4 w-px h-full bg-gradient-to-b from-transparent via-brand-primary/10 to-transparent" />
        </div>
      </section>

      {/* AESCE Section */}
      <section className="pb-24 pt-0 px-6 relative overflow-hidden -mt-16 md:-mt-32">
        <div className="max-w-7xl mx-auto relative z-10 flex flex-col items-center justify-center text-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            transition={{ duration: 1 }}
            className="relative"
          >
            {/* Glowing Orb Background */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] md:w-[500px] md:h-[500px] bg-brand-primary/20 rounded-full blur-[100px] animate-pulse" />

            <h2 className="text-6xl md:text-9xl font-black tracking-tighter text-transparent bg-clip-text bg-gradient-to-b from-white via-white to-white/10 relative z-10 mb-4">
              AESCE
            </h2>

            <motion.div
              initial={{ width: 0 }}
              whileInView={{ width: "100%" }}
              transition={{ duration: 1.5, delay: 0.5 }}
              className="h-px bg-gradient-to-r from-transparent via-brand-primary to-transparent w-full mb-6"
            />

            <p className="text-brand-primary font-mono text-sm md:text-xl tracking-[0.2em] uppercase glow-text">
              auto-evolution & synthesized consciousness engine
            </p>
          </motion.div>
        </div>

        {/* Particle/Grid VFX */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute inset-0 bg-[linear-gradient(rgba(0,255,65,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,255,65,0.03)_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:radial-gradient(ellipse_at_center,black_40%,transparent_80%)]" />
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-16 md:py-32 px-6">
        <div className="max-w-5xl mx-auto p-8 md:p-20 rounded-[40px] bg-brand-primary relative overflow-hidden group">
          <div className="relative z-10 text-black">
            <h2 className="text-3xl md:text-5xl lg:text-7xl font-bold tracking-tighter mb-6 md:mb-8 max-w-2xl">Ready to build the future?</h2>
            <p className="text-black/70 text-lg md:text-xl mb-8 md:mb-12 max-w-xl font-medium">Join 50,000+ developers building the next generation of astra applications.</p>
          </div>

          {/* Decorative elements */}
          <div className="absolute top-0 right-0 w-96 h-96 bg-white/20 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-black/5 rounded-full blur-2xl translate-y-1/2 -translate-x-1/2" />
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 md:py-20 px-6 border-t border-white/5">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-start gap-8 md:gap-12">
          <div className="space-y-6">
            <div className="flex items-center gap-2">
              <CustomLogo className="text-white w-6 h-6" />
              <span className="font-bold text-lg tracking-tighter lowercase" style={{ fontFamily: 'var(--font-logo)' }}>astra agent</span>
            </div>
            <p className="text-white/40 text-sm max-w-xs">Building the infrastructure for the astra economy. Recursive, resilient, and ready.</p>
            <div className="group flex items-center gap-3 px-4 py-2 rounded-full border border-white/10 bg-white/5 hover:bg-white/10 hover:border-brand-primary/50 transition-all duration-300 cursor-pointer w-fit backdrop-blur-sm">
              <div className="relative w-5 h-5 rounded-full overflow-hidden border border-white/20 group-hover:border-brand-primary transition-colors shadow-sm">
                <img
                  src="https://flagcdn.com/w40/in.png"
                  alt="India"
                  className="w-full h-full object-cover scale-110"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-white/80 tracking-widest group-hover:text-white transition-colors">INDIA</span>
                <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.8)] animate-pulse"></div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-8 md:gap-20">
            <div className="space-y-4">
              <h4 className="text-xs font-bold uppercase tracking-widest text-white/40">Product</h4>
              <ul className="space-y-2 text-sm text-white/60">
                <li><a href="#" className="hover:text-brand-primary">Protocol</a></li>
                <li><a href="#" className="hover:text-brand-primary">Agents</a></li>
                <li><a href="#" className="hover:text-brand-primary">Network</a></li>
                <li><a href="#" className="hover:text-brand-primary">Pricing</a></li>
              </ul>
            </div>
            <div className="space-y-4">
              <h4 className="text-xs font-bold uppercase tracking-widest text-white/40">Contact</h4>
              <ul className="space-y-2 text-sm text-white/60">
                <li><a href="#" className="hover:text-brand-primary">Instagram</a></li>
                <li><a href="#" className="hover:text-brand-primary">Email</a></li>
                <li><a href="#" className="hover:text-brand-primary">Facebook</a></li>
                <li><a href="#" className="hover:text-brand-primary">Twitter</a></li>
              </ul>
            </div>
            <div className="space-y-4">
              <h4 className="text-xs font-bold uppercase tracking-widest text-white/40">Company</h4>
              <ul className="space-y-2 text-sm text-white/60">
                <li><a href="#" className="hover:text-brand-primary">About</a></li>
                <li><a href="#" className="hover:text-brand-primary">Careers</a></li>
                <li><a href="#" className="hover:text-brand-primary">Legal</a></li>
                <li><a href="#" className="hover:text-brand-primary">Privacy</a></li>
              </ul>
            </div>
          </div>
        </div>

        <div className="max-w-7xl mx-auto mt-20 pt-8 border-t border-white/5 flex flex-col sm:flex-row justify-between items-center gap-4 text-xs text-white/20 font-mono">
          <p>© 2026 ASTRA AGENT PROTOCOL. ALL RIGHTS RESERVED.</p>
          <div className="flex gap-6">
            <span>STATUS: ALL_SYSTEMS_OPERATIONAL</span>
            <span>BUILD: 0x8F2A9</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

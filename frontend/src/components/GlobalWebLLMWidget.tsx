import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, MessageSquare, Zap, Loader2, Send, Cpu } from 'lucide-react';
import { useWebLLM } from '../contexts/WebLLMContext';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

export const GlobalWebLLMWidget = () => {
    const [isOpen, setIsOpen] = useState(false);
    const { isLoaded, isLoading, progressText, loadModel, generateResponse } = useWebLLM();
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState<{ role: 'user' | 'assistant', content: string }[]>([]);
    const [isTyping, setIsTyping] = useState(false);
    const endOfMessagesRef = useRef<HTMLDivElement>(null);

    // Auto-scroll logic
    useEffect(() => {
        if (endOfMessagesRef.current) {
            endOfMessagesRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, isTyping]);

    const handleToggle = () => {
        setIsOpen(!isOpen);
        if (!isOpen && !isLoaded && !isLoading) {
            // Optional: Auto-load when they open it the first time
            // loadModel();
        }
    };

    const handleSend = async () => {
        if (!input.trim() || !isLoaded) return;

        const userPrompt = input.trim();
        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: userPrompt }]);

        setIsTyping(true);
        // Add empty assistant message to stream into
        setMessages(prev => [...prev, { role: 'assistant', content: '' }]);

        try {
            await generateResponse(userPrompt, (partialText) => {
                setMessages(currentList => {
                    const newList = [...currentList];
                    newList[newList.length - 1].content = partialText;
                    return newList;
                });
            });
        } catch (error) {
            setMessages(prev => {
                const newList = [...prev];
                newList[newList.length - 1].content = "⚠️ Inference failed. Ensure the model is fully loaded.";
                return newList;
            });
        } finally {
            setIsTyping(false);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <>
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: 20, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 20, scale: 0.95 }}
                        transition={{ type: "spring", stiffness: 300, damping: 25 }}
                        className="fixed bottom-24 right-6 w-[400px] h-[600px] max-h-[80vh] flex flex-col bg-black/80 backdrop-blur-2xl border border-brand-primary/30 rounded-2xl shadow-[0_0_40px_rgba(0,255,65,0.15)] z-[9999] overflow-hidden"
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
                            <div className="flex items-center gap-2">
                                <Cpu className="text-brand-primary w-5 h-5" />
                                <span className="font-mono font-bold tracking-tight text-white">EDGE AI CORTEX</span>
                                {isLoaded && <span className="w-2 h-2 bg-brand-primary rounded-full animate-pulse ml-2" />}
                            </div>
                            <button
                                onClick={() => setIsOpen(false)}
                                className="text-white/50 hover:text-white transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Content Area */}
                        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 crt-subtle">
                            {!isLoaded ? (
                                <div className="flex-1 flex flex-col items-center justify-center text-center p-6">
                                    <Zap className="w-12 h-12 text-brand-primary/50 mb-4" />
                                    <h3 className="font-bold text-lg mb-2 text-white">WebGPU Inference</h3>
                                    <p className="text-sm text-white/50 mb-6 font-mono">
                                        Run massive LLMs entirely locally in your browser. No API keys, absolute privacy.
                                    </p>

                                    {isLoading ? (
                                        <div className="w-full flex flex-col items-center gap-3">
                                            <Loader2 className="w-6 h-6 text-brand-primary animate-spin" />
                                            <span className="text-xs font-mono text-brand-primary">{progressText}</span>
                                        </div>
                                    ) : (
                                        <button
                                            onClick={loadModel}
                                            className="px-6 py-3 bg-brand-primary/10 text-brand-primary border border-brand-primary/50 hover:bg-brand-primary/20 hover:scale-105 transition-all rounded-lg font-mono text-sm font-bold uppercase tracking-widest flex items-center gap-2"
                                        >
                                            <Cpu className="w-4 h-4" />
                                            Initialize Engine
                                        </button>
                                    )}
                                </div>
                            ) : (
                                <>
                                    {messages.length === 0 && (
                                        <div className="text-center text-xs font-mono text-white/30 my-auto">
                                            Astra Edge Protocol Online. Ready for localized inference.
                                        </div>
                                    )}
                                    {messages.map((msg, idx) => (
                                        <div
                                            key={idx}
                                            className={`flex flex-col max-w-[85%] ${msg.role === 'user' ? 'self-end' : 'self-start'}`}
                                        >
                                            <div className={`p-3 rounded-xl text-sm ${msg.role === 'user' ? 'bg-brand-primary text-black ml-auto' : 'bg-white/10 text-white mr-auto border border-white/5'}`}>
                                                {msg.role === 'user' ? (
                                                    msg.content
                                                ) : (
                                                    <div className="prose prose-invert prose-sm max-w-none">
                                                        <ReactMarkdown
                                                            components={{
                                                                code({ node, inline, className, children, ...props }: any) {
                                                                    const match = /language-(\w+)/.exec(className || '');
                                                                    return !inline && match ? (
                                                                        <SyntaxHighlighter
                                                                            style={atomDark}
                                                                            language={match[1]}
                                                                            PreTag="div"
                                                                            className="rounded-md border border-white/10 !bg-black/50 overflow-x-auto text-[11px]"
                                                                            {...props}
                                                                        >
                                                                            {String(children).replace(/\n$/, '')}
                                                                        </SyntaxHighlighter>
                                                                    ) : (
                                                                        <code className="bg-white/10 px-1 py-0.5 rounded text-brand-primary font-mono text-xs" {...props}>
                                                                            {children}
                                                                        </code>
                                                                    );
                                                                }
                                                            }}
                                                        >
                                                            {msg.content}
                                                        </ReactMarkdown>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                    <div ref={endOfMessagesRef} />
                                </>
                            )}
                        </div>

                        {/* Input Area */}
                        <div className="p-4 bg-black/50 border-t border-white/10">
                            <div className="relative">
                                <textarea
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    placeholder={isLoaded ? "Query the local cortex..." : "Initialize engine to chat"}
                                    disabled={!isLoaded || isTyping}
                                    className="w-full bg-white/5 border border-white/10 rounded-xl py-3 pl-4 pr-12 text-sm text-white placeholder-white/30 focus:outline-none focus:border-brand-primary/50 resize-none min-h-[50px] max-h-[120px] font-mono disabled:opacity-50"
                                    rows={1}
                                />
                                <button
                                    onClick={handleSend}
                                    disabled={!isLoaded || !input.trim() || isTyping}
                                    className="absolute right-2 bottom-2 p-2 bg-brand-primary text-black rounded-lg disabled:opacity-30 disabled:bg-white/10 disabled:text-white"
                                >
                                    <Send className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Floating Toggle Button */}
            <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleToggle}
                className="fixed bottom-6 right-6 w-14 h-14 bg-brand-primary text-black rounded-full flex items-center justify-center shadow-[0_0_20px_rgba(0,255,65,0.4)] z-[9999] group overflow-hidden border-2 border-black"
            >
                <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
                {isOpen ? (
                    <X className="w-6 h-6 relative z-10" />
                ) : (
                    <Cpu className="w-6 h-6 stroke-[2.5] relative z-10" />
                )}
                {/* Glow ring */}
                <div className="absolute -inset-1 border border-brand-primary rounded-full animate-ping opacity-20 hidden group-hover:block" />
            </motion.button>
        </>
    );
};

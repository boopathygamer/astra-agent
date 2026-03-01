import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
    X,
    User,
    Key,
    Plus,
    Trash2,
    Eye,
    EyeOff,
    Save,
    CheckCircle2,
    AlertCircle,
    Loader2,
    Shield,
    Zap,
} from 'lucide-react';
import { saveApiKeys, getApiKeyStatus } from './services/api';

// ── Types ─────────────────────────────────────

interface ApiKeyRow {
    id: string;
    apiKey: string;
    showKey: boolean;
}

interface ProviderStatus {
    provider: string;
    active: boolean;
}

type SettingsTab = 'account' | 'api';

// ── Component ─────────────────────────────────

export default function SettingsModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
    const [activeTab, setActiveTab] = useState<SettingsTab>('account');
    const [apiKeys, setApiKeys] = useState<ApiKeyRow[]>([createEmptyRow()]);
    const [saving, setSaving] = useState(false);
    const [saveResult, setSaveResult] = useState<{ ok: boolean; msg: string } | null>(null);
    const [providerStatuses, setProviderStatuses] = useState<ProviderStatus[]>([]);
    const overlayRef = useRef<HTMLDivElement>(null);

    // Load saved keys from localStorage on mount
    useEffect(() => {
        if (!isOpen) return;
        const stored = localStorage.getItem('astra_api_keys_v2');
        if (stored) {
            try {
                const parsed: ApiKeyRow[] = JSON.parse(stored);
                if (parsed.length > 0) setApiKeys(parsed.map(k => ({ ...k, showKey: false })));
            } catch { /* ignore */ }
        }
        getApiKeyStatus()
            .then(res => setProviderStatuses(res.providers || []))
            .catch(() => { });
    }, [isOpen]);

    const handleBackdropClick = (e: React.MouseEvent) => {
        if (e.target === overlayRef.current) onClose();
    };

    useEffect(() => {
        const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [onClose]);

    function createEmptyRow(): ApiKeyRow {
        return {
            id: `key-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            apiKey: '',
            showKey: false,
        };
    }

    const addRow = () => {
        if (apiKeys.length >= 5) return;
        setApiKeys(prev => [...prev, createEmptyRow()]);
    };

    const removeRow = (id: string) => {
        if (apiKeys.length <= 1) return;
        setApiKeys(prev => prev.filter(k => k.id !== id));
    };

    const updateRow = (id: string, field: keyof ApiKeyRow, value: string | boolean) => {
        setApiKeys(prev => prev.map(k => k.id === id ? { ...k, [field]: value } : k));
    };

    // Auto-detect provider hint from key prefix (display only)
    function detectHint(key: string): { label: string; color: string } {
        const k = key.trim();
        if (k.startsWith('sk-ant-')) return { label: 'Anthropic', color: '#d4a574' };
        if (k.startsWith('AIzaSy')) return { label: 'Gemini', color: '#4285f4' };
        if (k.startsWith('sk-')) return { label: 'OpenAI', color: '#10a37f' };
        if (k.length > 10) return { label: 'API Key', color: '#8b8b8b' };
        return { label: '', color: '' };
    }

    const handleSave = async () => {
        const validKeys = apiKeys.filter(k => k.apiKey.trim());
        if (validKeys.length === 0) {
            setSaveResult({ ok: false, msg: 'Please enter at least one API key' });
            setTimeout(() => setSaveResult(null), 3000);
            return;
        }

        setSaving(true);
        setSaveResult(null);

        try {
            const keyStrings = validKeys.map(k => k.apiKey.trim());
            localStorage.setItem('astra_api_keys_v2', JSON.stringify(apiKeys));
            const result = await saveApiKeys(keyStrings);
            setSaveResult({
                ok: true,
                msg: `${result.activated} provider${result.activated !== 1 ? 's' : ''} activated — full power unlocked!`,
            });
            const status = await getApiKeyStatus();
            setProviderStatuses(status.providers || []);
        } catch (err) {
            setSaveResult({ ok: false, msg: err instanceof Error ? err.message : 'Failed to save keys' });
        } finally {
            setSaving(false);
            setTimeout(() => setSaveResult(null), 4000);
        }
    };

    const activeCount = providerStatuses.filter(p => p.active).length;

    return (
        <AnimatePresence>
            {isOpen && (
                <motion.div
                    ref={overlayRef}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    onClick={handleBackdropClick}
                    className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
                >
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 20 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        exit={{ scale: 0.95, opacity: 0, y: 20 }}
                        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                        className="w-full max-w-2xl max-h-[85vh] bg-[#111111] border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col"
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
                            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                                <Shield className="w-5 h-5 text-emerald-400" />
                                Settings
                            </h2>
                            <button
                                onClick={onClose}
                                className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Tab Navigation */}
                        <div className="flex border-b border-white/10">
                            <button
                                onClick={() => setActiveTab('account')}
                                className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors relative ${activeTab === 'account'
                                    ? 'text-emerald-400'
                                    : 'text-white/50 hover:text-white/80'
                                    }`}
                            >
                                <User className="w-4 h-4" />
                                Account
                                {activeTab === 'account' && (
                                    <motion.div
                                        layoutId="settings-tab"
                                        className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-400"
                                    />
                                )}
                            </button>
                            <button
                                onClick={() => setActiveTab('api')}
                                className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-colors relative ${activeTab === 'api'
                                    ? 'text-emerald-400'
                                    : 'text-white/50 hover:text-white/80'
                                    }`}
                            >
                                <Key className="w-4 h-4" />
                                API Keys
                                {activeCount > 0 && (
                                    <span className="ml-1 px-1.5 py-0.5 text-[10px] font-bold bg-emerald-500/20 text-emerald-400 rounded-full">
                                        {activeCount}
                                    </span>
                                )}
                                {activeTab === 'api' && (
                                    <motion.div
                                        layoutId="settings-tab"
                                        className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-400"
                                    />
                                )}
                            </button>
                        </div>

                        {/* Content */}
                        <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
                            <AnimatePresence mode="wait">
                                {activeTab === 'account' ? (
                                    <motion.div
                                        key="account"
                                        initial={{ opacity: 0, x: -20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        exit={{ opacity: 0, x: 20 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        <div className="bg-white/5 border border-white/10 rounded-xl p-6">
                                            <div className="flex items-center gap-4">
                                                <div className="w-16 h-16 rounded-full bg-emerald-500 flex items-center justify-center text-2xl font-bold text-black shadow-lg shadow-emerald-500/20">
                                                    BG
                                                </div>
                                                <div>
                                                    <h3 className="text-xl font-semibold text-white">Boopathy Gamer</h3>
                                                    <span className="inline-flex items-center gap-1.5 mt-1 px-3 py-1 bg-emerald-500/10 text-emerald-400 text-xs font-bold rounded-full border border-emerald-500/20">
                                                        <Zap className="w-3 h-3" />
                                                        Pro Plan
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="mt-6 grid grid-cols-2 gap-4">
                                                <div className="bg-white/5 rounded-lg p-4 border border-white/5">
                                                    <p className="text-xs text-white/40 uppercase tracking-wider font-medium">Status</p>
                                                    <p className="text-sm text-white mt-1 font-medium">Active</p>
                                                </div>
                                                <div className="bg-white/5 rounded-lg p-4 border border-white/5">
                                                    <p className="text-xs text-white/40 uppercase tracking-wider font-medium">API Keys</p>
                                                    <p className="text-sm text-white mt-1 font-medium">{activeCount} active</p>
                                                </div>
                                            </div>
                                        </div>
                                    </motion.div>
                                ) : (
                                    <motion.div
                                        key="api"
                                        initial={{ opacity: 0, x: 20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        exit={{ opacity: 0, x: -20 }}
                                        transition={{ duration: 0.2 }}
                                    >
                                        {/* Info Banner */}
                                        <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-4 mb-5 flex items-start gap-3">
                                            <Zap className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                                            <div>
                                                <p className="text-sm text-white/80 font-medium">Unlock Full Power</p>
                                                <p className="text-xs text-white/40 mt-1 leading-relaxed">
                                                    Paste 1–5 API keys below. The system auto-detects your provider (OpenAI, Gemini, Anthropic, or any OpenAI-compatible API) and activates 100% backend power.
                                                </p>
                                            </div>
                                        </div>

                                        {/* API Key Rows */}
                                        <div className="space-y-3">
                                            {apiKeys.map((row, index) => {
                                                const hint = detectHint(row.apiKey);
                                                return (
                                                    <motion.div
                                                        key={row.id}
                                                        initial={{ opacity: 0, y: 10 }}
                                                        animate={{ opacity: 1, y: 0 }}
                                                        exit={{ opacity: 0, y: -10 }}
                                                        transition={{ delay: index * 0.05 }}
                                                        className="bg-white/5 border border-white/10 rounded-xl p-4 group hover:border-white/20 transition-colors"
                                                    >
                                                        {/* Label + detected provider */}
                                                        <div className="flex items-center justify-between mb-3">
                                                            <div className="flex items-center gap-2">
                                                                {hint.color && (
                                                                    <div
                                                                        className="w-2.5 h-2.5 rounded-full transition-colors"
                                                                        style={{ backgroundColor: hint.color }}
                                                                    />
                                                                )}
                                                                <span className="text-sm font-medium text-white/70">
                                                                    API Key {index + 1}
                                                                </span>
                                                                {hint.label && (
                                                                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-white/40 font-mono">
                                                                        {hint.label}
                                                                    </span>
                                                                )}
                                                            </div>

                                                            {apiKeys.length > 1 && (
                                                                <button
                                                                    onClick={() => removeRow(row.id)}
                                                                    className="p-1.5 rounded-lg text-white/20 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
                                                                >
                                                                    <Trash2 className="w-3.5 h-3.5" />
                                                                </button>
                                                            )}
                                                        </div>

                                                        {/* API Key Input */}
                                                        <div className="relative">
                                                            <input
                                                                type={row.showKey ? 'text' : 'password'}
                                                                value={row.apiKey}
                                                                onChange={(e) => updateRow(row.id, 'apiKey', e.target.value)}
                                                                placeholder="Paste your API key here..."
                                                                className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-2.5 text-sm text-white placeholder-white/20 outline-none focus:border-emerald-500/50 focus:bg-black/50 transition-all font-mono pr-10"
                                                                spellCheck={false}
                                                                autoComplete="off"
                                                            />
                                                            <button
                                                                type="button"
                                                                onClick={() => updateRow(row.id, 'showKey', !row.showKey)}
                                                                className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
                                                            >
                                                                {row.showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                                            </button>
                                                        </div>
                                                    </motion.div>
                                                );
                                            })}
                                        </div>

                                        {/* Add Key Button */}
                                        {apiKeys.length < 5 && (
                                            <button
                                                onClick={addRow}
                                                className="w-full mt-3 py-2.5 border border-dashed border-white/10 rounded-xl text-sm text-white/40 hover:text-white/70 hover:border-white/20 hover:bg-white/5 transition-all flex items-center justify-center gap-2"
                                            >
                                                <Plus className="w-4 h-4" />
                                                Add API Key ({apiKeys.length}/5)
                                            </button>
                                        )}

                                        {/* Save Result */}
                                        <AnimatePresence>
                                            {saveResult && (
                                                <motion.div
                                                    initial={{ opacity: 0, y: 10 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    exit={{ opacity: 0, y: -10 }}
                                                    className={`mt-4 flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-medium ${saveResult.ok
                                                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                                        : 'bg-red-500/10 text-red-400 border border-red-500/20'
                                                        }`}
                                                >
                                                    {saveResult.ok ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                                                    {saveResult.msg}
                                                </motion.div>
                                            )}
                                        </AnimatePresence>

                                        {/* Save Button */}
                                        <button
                                            onClick={handleSave}
                                            disabled={saving}
                                            className="w-full mt-5 py-3 bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-sm rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                                        >
                                            {saving ? (
                                                <>
                                                    <Loader2 className="w-4 h-4 animate-spin" />
                                                    Activating...
                                                </>
                                            ) : (
                                                <>
                                                    <Save className="w-4 h-4" />
                                                    Save & Activate
                                                </>
                                            )}
                                        </button>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

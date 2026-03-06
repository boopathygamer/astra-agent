import React, { useState, useCallback, useRef } from 'react';
import {
    X, Github, FolderUp, Loader2, CheckCircle2, XCircle, AlertTriangle,
    FileCode, FolderOpen, ArrowRight, Upload, Globe, Smartphone, Gamepad2, Search
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

// ── Types ──
export type UploaderMode = 'app' | 'web' | 'game';

interface UploadedFile {
    name: string;
    path: string;
    size: number;
    content: string;
}

interface AnalysisResult {
    compatible: boolean;
    projectType: string;
    language: string;
    framework: string;
    fileCount: number;
    totalSize: number;
    issues: { severity: 'error' | 'warning' | 'info'; message: string }[];
    summary: string;
}

interface ProjectUploaderProps {
    mode: UploaderMode;
    isOpen: boolean;
    onClose: () => void;
    onImport: (files: UploadedFile[], analysis: AnalysisResult) => void;
}

// ── Mode Configs ──
const MODE_CONFIG: Record<UploaderMode, {
    label: string;
    icon: typeof Globe;
    color: string;
    gradient: string;
    accepts: string[];
    rejects: { patterns: RegExp[]; message: string }[];
}> = {
    app: {
        label: 'App Studio',
        icon: Smartphone,
        color: 'blue',
        gradient: 'from-blue-500 to-cyan-500',
        accepts: ['React Native', 'Flutter', 'Swift', 'Kotlin', 'Dart', 'TypeScript', 'JavaScript'],
        rejects: [],
    },
    web: {
        label: 'Web Studio',
        icon: Globe,
        color: 'emerald',
        gradient: 'from-emerald-500 to-teal-500',
        accepts: ['HTML', 'CSS', 'JavaScript', 'TypeScript', 'React', 'Vue', 'Next.js', 'Svelte'],
        rejects: [],
    },
    game: {
        label: 'Game Studio',
        icon: Gamepad2,
        color: 'orange',
        gradient: 'from-orange-500 to-amber-500',
        accepts: ['C++', 'C', 'HTML5 Canvas', '2D Game'],
        rejects: [
            {
                patterns: [
                    /three\.js/i, /threejs/i, /webgl/i, /babylon/i, /unity/i, /unreal/i,
                    /godot.*3d/i, /opengl.*3/i, /metal/i, /vulkan/i, /directx/i,
                    /\.fbx$/i, /\.obj$/i, /\.gltf$/i, /\.glb$/i, /\.blend$/i,
                    /3d\s*(game|render|engine|model|mesh|scene)/i,
                    /import\s+\*\s+as\s+THREE/i, /new\s+THREE\./i,
                    /WebGLRenderer/i, /PerspectiveCamera/i, /BoxGeometry/i,
                ],
                message: '❌ 3D games are not supported. This studio only supports 2D games for Android & iOS mobile. Detected 3D content in your project.',
            },
        ],
    },
};

// ── Analysis Engine ──
function analyzeProject(files: UploadedFile[], mode: UploaderMode): AnalysisResult {
    const config = MODE_CONFIG[mode];
    const issues: AnalysisResult['issues'] = [];
    const totalSize = files.reduce((s, f) => s + f.size, 0);
    const allContent = files.map(f => f.content).join('\n');
    const allNames = files.map(f => f.name.toLowerCase());

    // Detect language & framework
    let language = 'Unknown';
    let framework = 'None';
    let projectType = 'Unknown';

    // Language detection
    const extCounts: Record<string, number> = {};
    files.forEach(f => {
        const ext = f.name.split('.').pop()?.toLowerCase() || '';
        extCounts[ext] = (extCounts[ext] || 0) + 1;
    });

    if (extCounts['cpp'] || extCounts['cc'] || extCounts['cxx'] || extCounts['h'] || extCounts['hpp']) {
        language = 'C++';
    } else if (extCounts['tsx'] || extCounts['ts']) {
        language = 'TypeScript';
    } else if (extCounts['jsx'] || extCounts['js']) {
        language = 'JavaScript';
    } else if (extCounts['dart']) {
        language = 'Dart';
    } else if (extCounts['swift']) {
        language = 'Swift';
    } else if (extCounts['kt'] || extCounts['kts']) {
        language = 'Kotlin';
    } else if (extCounts['py']) {
        language = 'Python';
    } else if (extCounts['html'] || extCounts['css']) {
        language = 'HTML/CSS';
    }

    // Framework detection
    if (allContent.includes('react-native') || allNames.some(n => n === 'app.json')) {
        framework = 'React Native';
        projectType = 'Mobile App';
    } else if (allContent.includes('flutter') || allNames.some(n => n === 'pubspec.yaml')) {
        framework = 'Flutter';
        projectType = 'Mobile App';
    } else if (allContent.includes('next') && allNames.some(n => n === 'next.config.js' || n === 'next.config.mjs')) {
        framework = 'Next.js';
        projectType = 'Web App';
    } else if (allContent.includes('from \'vue\'') || allContent.includes('from "vue"')) {
        framework = 'Vue.js';
        projectType = 'Web App';
    } else if (allContent.includes('from \'react\'') || allContent.includes('from "react"')) {
        framework = 'React';
        projectType = 'Web App';
    } else if (allNames.some(n => n === 'cmakelists.txt') && language === 'C++') {
        framework = 'CMake';
        projectType = '2D Game';
    } else if (allNames.some(n => n.endsWith('.html'))) {
        framework = 'Vanilla';
        projectType = 'Web Page';
    }

    // Check for rejections (e.g. 3D in game mode)
    for (const reject of config.rejects) {
        for (const pattern of reject.patterns) {
            const fileMatch = files.find(f => pattern.test(f.name) || pattern.test(f.content));
            if (fileMatch) {
                issues.push({ severity: 'error', message: reject.message });
                break;
            }
        }
    }

    // Compatibility check
    let compatible = issues.filter(i => i.severity === 'error').length === 0;

    // Mode-specific checks
    if (mode === 'game' && language !== 'C++' && language !== 'HTML/CSS' && language !== 'JavaScript') {
        issues.push({ severity: 'warning', message: `⚠️ Game Studio prefers C++ projects. Detected: ${language}. The agent will attempt to work with it but results may vary.` });
    }

    if (mode === 'app' && projectType === 'Web Page') {
        issues.push({ severity: 'warning', message: '⚠️ This looks like a web project, not a mobile app. The agent will attempt to convert it.' });
    }

    if (files.length === 0) {
        compatible = false;
        issues.push({ severity: 'error', message: '❌ No files found in the uploaded project.' });
    }

    // Info
    if (compatible && issues.length === 0) {
        issues.push({ severity: 'info', message: `✅ Project is compatible with ${config.label}. Ready to continue development.` });
    }

    const summary = compatible
        ? `${projectType} using ${framework} (${language}) — ${files.length} files, ${(totalSize / 1024).toFixed(1)} KB`
        : `Incompatible project: ${issues.find(i => i.severity === 'error')?.message || 'Unknown error'}`;

    return { compatible, projectType, language, framework, fileCount: files.length, totalSize, issues, summary };
}

// ── Component ──
export default function ProjectUploader({ mode, isOpen, onClose, onImport }: ProjectUploaderProps) {
    const [tab, setTab] = useState<'github' | 'folder'>('github');
    const [githubUrl, setGithubUrl] = useState('');
    const [loading, setLoading] = useState(false);
    const [files, setFiles] = useState<UploadedFile[]>([]);
    const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
    const [error, setError] = useState('');
    const fileInputRef = useRef<HTMLInputElement>(null);
    const config = MODE_CONFIG[mode];
    const ModeIcon = config.icon;

    const reset = useCallback(() => {
        setFiles([]);
        setAnalysis(null);
        setError('');
        setGithubUrl('');
        setLoading(false);
    }, []);

    const handleClose = useCallback(() => {
        reset();
        onClose();
    }, [onClose, reset]);

    // ── GitHub Import ──
    const handleGithubImport = useCallback(async () => {
        if (!githubUrl.trim()) return;
        setLoading(true);
        setError('');
        setAnalysis(null);

        try {
            // Validate URL
            const urlMatch = githubUrl.match(/github\.com\/([^/]+)\/([^/]+)/);
            if (!urlMatch) {
                setError('Invalid GitHub URL. Please enter a valid repository URL (e.g. https://github.com/user/repo)');
                setLoading(false);
                return;
            }

            const [, owner, repo] = urlMatch;
            const cleanRepo = repo.replace(/\.git$/, '');

            // Fetch repo contents via GitHub API
            const apiUrl = `https://api.github.com/repos/${owner}/${cleanRepo}/git/trees/main?recursive=1`;
            let response = await fetch(apiUrl);

            // Try 'master' branch if 'main' fails
            if (!response.ok) {
                const masterUrl = `https://api.github.com/repos/${owner}/${cleanRepo}/git/trees/master?recursive=1`;
                response = await fetch(masterUrl);
            }

            if (!response.ok) {
                setError(`Failed to fetch repository. Make sure it's a public repo. Status: ${response.status}`);
                setLoading(false);
                return;
            }

            const data = await response.json();
            const tree = data.tree || [];
            const codeFiles = tree.filter((f: any) =>
                f.type === 'blob' && f.size < 100000 &&
                /\.(tsx?|jsx?|html?|css|cpp|cc|cxx|h|hpp|c|py|dart|swift|kt|kts|json|yaml|yml|md|cmake|gradle|xml|plist)$/i.test(f.path)
            ).slice(0, 50); // Limit to 50 files

            // Fetch file contents (first 20 for analysis)
            const fetchedFiles: UploadedFile[] = [];
            const filesToFetch = codeFiles.slice(0, 20);

            for (const file of filesToFetch) {
                try {
                    const rawUrl = `https://raw.githubusercontent.com/${owner}/${cleanRepo}/main/${file.path}`;
                    let fileRes = await fetch(rawUrl);
                    if (!fileRes.ok) {
                        const masterRawUrl = `https://raw.githubusercontent.com/${owner}/${cleanRepo}/master/${file.path}`;
                        fileRes = await fetch(masterRawUrl);
                    }
                    if (fileRes.ok) {
                        const content = await fileRes.text();
                        fetchedFiles.push({
                            name: file.path.split('/').pop() || file.path,
                            path: file.path,
                            size: file.size,
                            content,
                        });
                    }
                } catch { /* skip failed files */ }
            }

            // Add remaining files as stubs
            codeFiles.slice(20).forEach((f: any) => {
                fetchedFiles.push({
                    name: f.path.split('/').pop() || f.path,
                    path: f.path,
                    size: f.size,
                    content: '',
                });
            });

            setFiles(fetchedFiles);
            const result = analyzeProject(fetchedFiles, mode);
            setAnalysis(result);
        } catch (err: any) {
            setError(`Failed to import: ${err?.message || 'Network error'}`);
        } finally {
            setLoading(false);
        }
    }, [githubUrl, mode]);

    // ── Folder Upload ──
    const handleFolderUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
        const fileList = e.target.files;
        if (!fileList || fileList.length === 0) return;

        setLoading(true);
        setError('');
        setAnalysis(null);

        try {
            const uploadedFiles: UploadedFile[] = [];
            const maxFiles = 50;
            const codeExtensions = /\.(tsx?|jsx?|html?|css|cpp|cc|cxx|h|hpp|c|py|dart|swift|kt|kts|json|yaml|yml|md|cmake|gradle|xml|plist)$/i;

            for (let i = 0; i < Math.min(fileList.length, maxFiles); i++) {
                const file = fileList[i];
                if (!codeExtensions.test(file.name)) continue;
                if (file.size > 100000) continue; // Skip >100KB files

                try {
                    const content = await file.text();
                    uploadedFiles.push({
                        name: file.name,
                        path: (file as any).webkitRelativePath || file.name,
                        size: file.size,
                        content,
                    });
                } catch { /* skip unreadable files */ }
            }

            setFiles(uploadedFiles);
            const result = analyzeProject(uploadedFiles, mode);
            setAnalysis(result);
        } catch (err: any) {
            setError(`Upload failed: ${err?.message || 'Unknown error'}`);
        } finally {
            setLoading(false);
        }
    }, [mode]);

    const handleImport = useCallback(() => {
        if (analysis?.compatible && files.length > 0) {
            onImport(files, analysis);
            handleClose();
        }
    }, [analysis, files, onImport, handleClose]);

    if (!isOpen) return null;

    const colorClass = config.color;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                onClick={handleClose}
            >
                <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: 20 }}
                    transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                    className="w-[560px] max-h-[85vh] bg-[#111] border border-white/[0.08] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
                    onClick={e => e.stopPropagation()}
                >
                    {/* Header */}
                    <div className="px-5 py-4 border-b border-white/[0.06] flex items-center justify-between shrink-0">
                        <div className="flex items-center gap-3">
                            <div className={`p-2 bg-gradient-to-br ${config.gradient} rounded-xl bg-opacity-20`} style={{ background: `linear-gradient(135deg, var(--tw-gradient-from) / 0.15, var(--tw-gradient-to) / 0.15)` }}>
                                <ModeIcon className="w-5 h-5 text-white/80" />
                            </div>
                            <div>
                                <h2 className="text-sm font-bold text-white">Import Project</h2>
                                <p className="text-[10px] text-white/30 mt-0.5">Upload to {config.label} for continued development</p>
                            </div>
                        </div>
                        <button onClick={handleClose} className="p-1.5 text-white/30 hover:text-white hover:bg-white/5 rounded-lg transition-colors">
                            <X className="w-4 h-4" />
                        </button>
                    </div>

                    {/* Tabs */}
                    <div className="px-5 pt-3 flex gap-1 shrink-0">
                        {([
                            { key: 'github' as const, Icon: Github, label: 'GitHub Repo' },
                            { key: 'folder' as const, Icon: FolderUp, label: 'Upload Folder' },
                        ]).map(({ key, Icon, label }) => (
                            <button key={key} onClick={() => { setTab(key); reset(); }}
                                className={`px-3 py-2 text-[12px] font-semibold rounded-lg flex items-center gap-2 transition-colors ${tab === key ? 'bg-white/10 text-white' : 'text-white/35 hover:text-white/60 hover:bg-white/5'
                                    }`}>
                                <Icon className="w-3.5 h-3.5" /> {label}
                            </button>
                        ))}
                    </div>

                    {/* Content */}
                    <div className="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-4">
                        {/* GitHub Tab */}
                        {tab === 'github' && (
                            <div className="space-y-3">
                                <div className="flex items-center gap-2">
                                    <div className="flex-1 relative">
                                        <Github className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/20" />
                                        <input
                                            type="text"
                                            value={githubUrl}
                                            onChange={e => setGithubUrl(e.target.value)}
                                            placeholder="https://github.com/user/repository"
                                            className="w-full bg-[#1a1a1a] border border-white/[0.08] rounded-xl pl-10 pr-4 py-2.5 text-[13px] text-white placeholder-white/20 outline-none focus:border-white/20 transition-colors"
                                            onKeyDown={e => { if (e.key === 'Enter') handleGithubImport(); }}
                                        />
                                    </div>
                                    <button
                                        onClick={handleGithubImport}
                                        disabled={!githubUrl.trim() || loading}
                                        className={`px-4 py-2.5 rounded-xl text-[12px] font-bold flex items-center gap-2 transition-all ${githubUrl.trim() && !loading
                                                ? `bg-gradient-to-r ${config.gradient} text-white shadow-lg hover:shadow-xl`
                                                : 'bg-white/5 text-white/15'
                                            }`}>
                                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                                        Pull
                                    </button>
                                </div>
                                <p className="text-[10px] text-white/20">
                                    Public repositories only. The agent will fetch and analyze the source code.
                                </p>
                            </div>
                        )}

                        {/* Folder Tab */}
                        {tab === 'folder' && (
                            <div className="space-y-3">
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    // @ts-ignore — webkitdirectory is a non-standard attribute
                                    webkitdirectory=""
                                    directory=""
                                    multiple
                                    onChange={handleFolderUpload}
                                    className="hidden"
                                />
                                <button
                                    onClick={() => fileInputRef.current?.click()}
                                    disabled={loading}
                                    className="w-full border-2 border-dashed border-white/[0.08] rounded-xl py-10 flex flex-col items-center justify-center gap-3 hover:border-white/15 hover:bg-white/[0.02] transition-all group cursor-pointer"
                                >
                                    {loading ? (
                                        <Loader2 className="w-8 h-8 text-white/30 animate-spin" />
                                    ) : (
                                        <div className={`p-3 rounded-xl bg-gradient-to-br ${config.gradient} bg-opacity-10`} style={{ background: `linear-gradient(135deg, var(--tw-gradient-from) / 0.1, var(--tw-gradient-to) / 0.1)` }}>
                                            <Upload className="w-6 h-6 text-white/50 group-hover:text-white/70 transition-colors" />
                                        </div>
                                    )}
                                    <div className="text-center">
                                        <p className="text-[13px] font-medium text-white/50 group-hover:text-white/70 transition-colors">
                                            {loading ? 'Analyzing project...' : 'Click to select project folder'}
                                        </p>
                                        <p className="text-[10px] text-white/20 mt-1">Source code files will be analyzed for compatibility</p>
                                    </div>
                                </button>
                            </div>
                        )}

                        {/* Error */}
                        {error && (
                            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                                className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 flex items-start gap-3">
                                <XCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                                <p className="text-[12px] text-red-300/80 leading-relaxed">{error}</p>
                            </motion.div>
                        )}

                        {/* Analysis Results */}
                        {analysis && (
                            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
                                {/* Summary Card */}
                                <div className={`rounded-xl border px-4 py-3 ${analysis.compatible
                                        ? 'bg-emerald-500/5 border-emerald-500/15'
                                        : 'bg-red-500/5 border-red-500/15'
                                    }`}>
                                    <div className="flex items-center gap-2 mb-2">
                                        {analysis.compatible
                                            ? <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                                            : <XCircle className="w-4 h-4 text-red-400" />
                                        }
                                        <span className={`text-[12px] font-bold ${analysis.compatible ? 'text-emerald-400' : 'text-red-400'}`}>
                                            {analysis.compatible ? 'COMPATIBLE' : 'INCOMPATIBLE'}
                                        </span>
                                    </div>
                                    <p className="text-[12px] text-white/60 leading-relaxed">{analysis.summary}</p>
                                </div>

                                {/* Project Details */}
                                <div className="grid grid-cols-2 gap-2">
                                    {[
                                        { label: 'Language', value: analysis.language },
                                        { label: 'Framework', value: analysis.framework },
                                        { label: 'Files', value: `${analysis.fileCount}` },
                                        { label: 'Size', value: `${(analysis.totalSize / 1024).toFixed(1)} KB` },
                                    ].map(({ label, value }) => (
                                        <div key={label} className="bg-white/[0.03] rounded-lg px-3 py-2 border border-white/[0.04]">
                                            <div className="text-[9px] font-bold text-white/25 uppercase tracking-wider">{label}</div>
                                            <div className="text-[12px] font-medium text-white/70 mt-0.5">{value}</div>
                                        </div>
                                    ))}
                                </div>

                                {/* Issues */}
                                {analysis.issues.map((issue, i) => (
                                    <div key={i} className={`flex items-start gap-2.5 px-3 py-2 rounded-lg border ${issue.severity === 'error' ? 'bg-red-500/5 border-red-500/10' :
                                            issue.severity === 'warning' ? 'bg-amber-500/5 border-amber-500/10' :
                                                'bg-cyan-500/5 border-cyan-500/10'
                                        }`}>
                                        {issue.severity === 'error' ? <XCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" /> :
                                            issue.severity === 'warning' ? <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" /> :
                                                <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 mt-0.5 shrink-0" />}
                                        <p className={`text-[11px] leading-relaxed ${issue.severity === 'error' ? 'text-red-300/80' :
                                                issue.severity === 'warning' ? 'text-amber-300/80' :
                                                    'text-cyan-300/80'
                                            }`}>{issue.message}</p>
                                    </div>
                                ))}

                                {/* File Tree */}
                                {files.length > 0 && (
                                    <div className="bg-white/[0.02] rounded-xl border border-white/[0.04] overflow-hidden">
                                        <div className="px-3 py-2 border-b border-white/[0.04] flex items-center gap-2">
                                            <FolderOpen className="w-3 h-3 text-amber-400/60" />
                                            <span className="text-[10px] font-bold text-white/30 uppercase tracking-wider">Project Files</span>
                                            <span className="text-[9px] text-white/15 ml-auto">{files.length} files</span>
                                        </div>
                                        <div className="max-h-[140px] overflow-y-auto custom-scrollbar">
                                            {files.slice(0, 30).map((f, i) => (
                                                <div key={i} className="flex items-center gap-2 px-3 py-1 hover:bg-white/[0.02] border-b border-white/[0.02] last:border-0">
                                                    <FileCode className="w-3 h-3 text-white/15 shrink-0" />
                                                    <span className="text-[10px] text-white/40 font-mono truncate flex-1">{f.path}</span>
                                                    <span className="text-[9px] text-white/15 shrink-0">{(f.size / 1024).toFixed(1)}k</span>
                                                </div>
                                            ))}
                                            {files.length > 30 && (
                                                <div className="px-3 py-1.5 text-[9px] text-white/15 text-center">
                                                    +{files.length - 30} more files
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </div>

                    {/* Footer */}
                    {analysis && (
                        <div className="px-5 py-3 border-t border-white/[0.06] flex items-center justify-between shrink-0 bg-[#0c0c0c]">
                            <button onClick={reset}
                                className="px-3 py-1.5 text-[11px] font-medium text-white/40 hover:text-white/60 hover:bg-white/5 rounded-lg transition-colors">
                                Reset
                            </button>
                            <button
                                onClick={handleImport}
                                disabled={!analysis.compatible}
                                className={`px-4 py-2 rounded-xl text-[12px] font-bold flex items-center gap-2 transition-all ${analysis.compatible
                                        ? `bg-gradient-to-r ${config.gradient} text-white shadow-lg hover:shadow-xl`
                                        : 'bg-white/5 text-white/15 cursor-not-allowed'
                                    }`}>
                                {analysis.compatible ? (
                                    <>
                                        <ArrowRight className="w-3.5 h-3.5" /> Continue Development
                                    </>
                                ) : (
                                    <>
                                        <XCircle className="w-3.5 h-3.5" /> Incompatible
                                    </>
                                )}
                            </button>
                        </div>
                    )}
                </motion.div>
            </motion.div>
        </AnimatePresence>
    );
}

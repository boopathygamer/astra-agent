/**
 * Centralized API Client — Connects frontend to the FastAPI backend.
 * All backend communication goes through this module.
 */

const API_BASE = (import.meta as any).env?.VITE_API_URL || '';

// ── Helper ──────────────────────────────────────

interface FetchOptions {
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
}

async function apiFetch<T = any>(path: string, opts: FetchOptions = {}): Promise<T> {
    const { method = 'GET', body, headers = {} } = opts;

    const _MAX_RETRIES = 3;
    const _TIMEOUT_MS = 30_000; // 30-second request timeout
    const _BACKOFF_BASE = 1000; // 1 second

    let lastError: Error | null = null;

    for (let attempt = 0; attempt < _MAX_RETRIES; attempt++) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), _TIMEOUT_MS);

        try {
            const res = await fetch(`${API_BASE}${path}`, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    ...headers,
                },
                body: body ? JSON.stringify(body) : undefined,
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            if (!res.ok) {
                let detail = `Request failed (${res.status})`;
                try {
                    const err = await res.json();
                    detail = err.detail || err.error || detail;
                } catch { /* ignore parse errors */ }

                // Don't retry client errors (4xx), only server errors (5xx)
                if (res.status >= 400 && res.status < 500) {
                    throw new Error(detail);
                }
                throw new Error(detail);
            }

            return res.json();
        } catch (err: any) {
            clearTimeout(timeoutId);
            lastError = err;

            // Don't retry AbortErrors from user cancellation (only timeout)
            const isTimeout = err.name === 'AbortError';
            const isNetworkError = err.message?.includes('Failed to fetch') || err.message?.includes('NetworkError');

            if ((isTimeout || isNetworkError) && attempt < _MAX_RETRIES - 1) {
                const backoff = _BACKOFF_BASE * (2 ** attempt);
                await new Promise(resolve => setTimeout(resolve, backoff));
                continue;
            }

            throw err;
        }
    }

    throw lastError || new Error('Request failed after retries');
}

// ── Health ───────────────────────────────────────

export interface HealthStatus {
    status: string;
    model_loaded: boolean;
    vision_ready: boolean;
    memory_entries: number;
    tools_available: number;
}

export async function checkHealth(): Promise<HealthStatus> {
    return apiFetch<HealthStatus>('/health');
}

// ── Chat ────────────────────────────────────────

export interface ChatResponse {
    answer: string;
    confidence: number;
    iterations: number;
    mode: string;
    thinking_steps: string[];
    tools_used: string[];
    duration_ms: number;
    routed_to?: string;
    routing_confidence?: number;
    routing_display?: string;
    routing_emoji?: string;
}

export async function sendChat(
    message: string,
    useThinking: boolean = true,
): Promise<ChatResponse> {
    const startTime = Date.now();
    try {
        return await apiFetch<ChatResponse>('/chat', {
            method: 'POST',
            body: { message, use_thinking: useThinking },
        });
    } catch (error: any) {
        // ── OFFLINE FALLBACK ──
        // If the backend fails (NetworkError, Server Down, No API keys) and the user has loaded WebLLM
        if (typeof window !== 'undefined' && window._webLlmEngine) {
            console.warn("Backend API failed. Routing request to local WebLLM Edge Agent.");
            try {
                const engine = window._webLlmEngine;
                const reply = await engine.chat.completions.create({
                    messages: [
                        { role: "system", content: "You are the Astra Edge Agent. You run locally in the user's browser. You are an expert at coding, architecture, and generating full HTML/JS/CSS applications. Always output working code if requested." },
                        { role: "user", content: message }
                    ]
                });

                const offlineAnswer = reply.choices[0]?.message.content || "Offline inference failed.";

                return {
                    answer: offlineAnswer,
                    confidence: 1.0,
                    iterations: 1,
                    mode: 'direct',
                    thinking_steps: [
                        `Backend unreachable: ${error.message || 'Network error'}`,
                        "Intercepted failure natively in browser",
                        "Routing to WebGPU / WebLLM Edge Core..."
                    ],
                    tools_used: ['webllm_edge_inference'],
                    duration_ms: Date.now() - startTime,
                    // These custom properties let the UI show an offline badge
                    routed_to: 'WebLLM (Offline Edge Engine)',
                    routing_emoji: '⚡'
                };
            } catch (fallbackError) {
                console.error("Offline WebLLM fallback also failed:", fallbackError);
            }
        }

        // If we reach here, either WebLLM isn't loaded or it failed too
        throw error;
    }
}

// ── Providers ───────────────────────────────────

export interface ProviderKeys {
    openai_api_key?: string;
    claude_api_key?: string;
    gemini_api_key?: string;
    grok_api_key?: string;
    openrouter_api_key?: string;
    openrouter_model?: string;
}

export interface ConfigureResult {
    status: string;
    providers_updated: string[];
    active_providers: string[];
    council_mode: boolean;
    council_size: number;
    active_provider: string;
}

export async function configureProviders(keys: ProviderKeys): Promise<ConfigureResult> {
    return apiFetch<ConfigureResult>('/providers/configure', {
        method: 'POST',
        body: keys,
    });
}

export interface ProviderStatusResponse {
    status: string;
    providers: any[];
    active_provider: string;
    council_mode: boolean;
    council_stats: any;
}

export async function getProviderStatus(): Promise<ProviderStatusResponse> {
    return apiFetch<ProviderStatusResponse>('/providers/status');
}

// ── Agent ───────────────────────────────────────

export interface AgentTaskResponse {
    answer: string;
    confidence: number;
    iterations: number;
    mode: string;
    tools_used: any[];
    thinking_trace: any;
    duration_ms: number;
}

export async function submitAgentTask(
    task: string,
    useThinking: boolean = true,
    maxToolCalls: number = 10,
): Promise<AgentTaskResponse> {
    return apiFetch<AgentTaskResponse>('/agent/task', {
        method: 'POST',
        body: { task, use_thinking: useThinking, max_tool_calls: maxToolCalls },
    });
}

// ── Tutor ───────────────────────────────────────

export interface TutorStartResponse {
    session_id: string;
    topic: string;
    greeting: string;
    [key: string]: any;
}

export interface TutorRespondResponse {
    response: string;
    [key: string]: any;
}

export async function startTutor(topic: string): Promise<TutorStartResponse> {
    return apiFetch<TutorStartResponse>('/tutor/start', {
        method: 'POST',
        body: { topic },
    });
}

export async function respondTutor(
    sessionId: string,
    message: string,
): Promise<TutorRespondResponse> {
    return apiFetch<TutorRespondResponse>('/tutor/respond', {
        method: 'POST',
        body: { session_id: sessionId, message },
    });
}

// ── Swarm ───────────────────────────────────────

export async function executeSwarm(task: string, roles?: string[]): Promise<any> {
    return apiFetch('/swarm/execute', {
        method: 'POST',
        body: { task, roles },
    });
}

// ── Memory ──────────────────────────────────────

export async function getMemoryStats(): Promise<any> {
    return apiFetch('/memory/stats');
}

export async function recallMemory(query: string): Promise<any> {
    return apiFetch('/memory/recall', {
        method: 'POST',
        body: { query },
    });
}

// ── Agent Stats ─────────────────────────────────

export async function getAgentStats(): Promise<any> {
    return apiFetch('/agent/stats');
}

// ── Processes ───────────────────────────────────

export async function getProcesses(): Promise<any> {
    return apiFetch('/processes');
}

// ── Sessions ────────────────────────────────────

export async function getSessions(): Promise<any> {
    return apiFetch('/sessions');
}

// ── Long-Term Memory ────────────────────────────

export async function getLongTermMemory(): Promise<any> {
    return apiFetch('/memory/long-term');
}

// ── Devices ─────────────────────────────────────

export async function getDeviceList(): Promise<any> {
    return apiFetch('/device/list');
}

// ── Security Scanner ────────────────────────────

export async function scanFile(filePath: string): Promise<any> {
    return apiFetch('/scan/file', { method: 'POST', body: { file_path: filePath } });
}

export async function scanDirectory(directory: string, recursive: boolean = true, maxFiles: number = 100): Promise<any> {
    return apiFetch('/scan/directory', { method: 'POST', body: { directory, recursive, max_files: maxFiles } });
}

export async function scanUrl(url: string): Promise<any> {
    return apiFetch('/scan/url', { method: 'POST', body: { url } });
}

export async function getScanStats(): Promise<any> {
    return apiFetch('/scan/stats');
}

export async function getScanHistory(): Promise<any> {
    return apiFetch('/scan/history');
}

export async function quarantineFile(filePath: string): Promise<any> {
    return apiFetch('/scan/quarantine', { method: 'POST', body: { file_path: filePath } });
}

export async function destroyThreat(filePath: string): Promise<any> {
    return apiFetch('/scan/destroy', { method: 'POST', body: { file_path: filePath } });
}

// ── Multi-Agent Orchestrator ────────────────────

export interface OrchestrateResult {
    strategy: string;
    topic: string;
    answer: string;
    confidence: number;
    mode?: string;
    error?: string;
    duration_ms: number;
    sub_tasks?: number;
    summary?: string;
}

export async function orchestrateDebate(topic: string, strategy: string = 'debate'): Promise<OrchestrateResult> {
    return apiFetch<OrchestrateResult>('/orchestrate/debate', {
        method: 'POST',
        body: { topic, strategy },
    });
}

export interface OrchestratorStatus {
    available_strategies: string[];
    agent_initialized: boolean;
    routing_stats: any;
}

export async function getOrchestratorStatus(): Promise<OrchestratorStatus> {
    return apiFetch<OrchestratorStatus>('/orchestrate/status');
}

// ── MCP (Model Context Protocol) ────────────────

export async function getMcpConfig(client: string = 'claude'): Promise<any> {
    return apiFetch(`/mcp/config?client=${encodeURIComponent(client)}`);
}

export interface McpTool {
    name: string;
    description: string;
}

export interface McpStatus {
    project_root: string;
    transports: string[];
    stdio_command: string;
    http_command: string;
    http_url: string;
    tools_count: number;
    tools: McpTool[];
    agent_initialized: boolean;
}

export async function getMcpStatus(): Promise<McpStatus> {
    return apiFetch<McpStatus>('/mcp/status');
}

// ── Dev Studio: Model Validation ────────────────

export interface ModelValidation {
    eligible: boolean;
    model: string;
    reason: string;
    capabilities: string[];
}

export async function validateModel(): Promise<ModelValidation> {
    return apiFetch<ModelValidation>('/dev/validate-model', { method: 'POST' });
}

// ── Dev Studio: GitHub Push ─────────────────────

export interface GeneratedFilePayload {
    path: string;
    content: string;
}

export interface GitHubPushResult {
    success: boolean;
    message: string;
    commit_sha?: string;
}

export async function githubPush(
    repoUrl: string,
    token: string,
    files: GeneratedFilePayload[],
    commitMessage: string = 'feat: generated by ASTRA Builder'
): Promise<GitHubPushResult> {
    return apiFetch<GitHubPushResult>('/dev/github-push', {
        method: 'POST',
        body: { repo_url: repoUrl, token, files, commit_message: commitMessage },
    });
}

// ── Dev Studio: APK Build ───────────────────────

export interface ApkBuildResult {
    success: boolean;
    download_url?: string;
    apk_base64?: string;
    size_mb?: number;
    message?: string;
}

export async function buildApk(
    html: string,
    appName: string,
    packageName: string
): Promise<ApkBuildResult> {
    return apiFetch<ApkBuildResult>('/dev/build-apk', {
        method: 'POST',
        body: { html, app_name: appName, package_name: packageName },
    });
}


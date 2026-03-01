/**
 * API Client — Super System Backend Integration
 * ═══════════════════════════════════════════════
 * Central service layer connecting the Astra Agent frontend
 * to all Super System backend endpoints with full power.
 */

// ── Types ──────────────────────────────────────

export interface ChatResponse {
  answer: string;
  confidence: number;
  iterations: number;
  mode: string;
  thinking_steps: string[];
  tools_used: string[];
  duration_ms: number;
}

export interface AgentTaskResponse {
  answer: string;
  confidence: number;
  iterations: number;
  mode: string;
  tools_used: { tool: string; result: string }[];
  thinking_trace: {
    iterations: number;
    final_confidence: number;
    mode: string;
    steps: { iteration: number; action: string; confidence: number }[];
  } | null;
  duration_ms: number;
}

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  vision_ready: boolean;
  memory_entries: number;
  tools_available: number;
}

export interface MemoryStatsResponse {
  total_failures: number;
  total_successes: number;
  regression_tests: number;
  category_weights: Record<string, number>;
  most_retrieved: unknown[];
}

export interface TutorStartResponse {
  session_id: string;
  topic: string;
  difficulty: string;
  question: string;
  context: string;
  hints_remaining: number;
}

export interface TutorRespondResponse {
  evaluation: string;
  score: number;
  feedback: string;
  next_question: string;
  hints_remaining: number;
  session_complete: boolean;
}

export interface SwarmResult {
  task: string;
  agents: { role: string; contribution: string }[];
  merged_solution: string;
  duration_ms: number;
}

export interface ForgeResult {
  success: boolean;
  forge_id?: string;
  name?: string;
  description?: string;
  test_output?: string;
  error?: string;
}

export interface ProcessInfo {
  process_id: string;
  status: string;
  command: string;
  started_at: string;
}

// ── SSE Stream Event Types ──────────────────────

export interface StreamChunk {
  type: 'text' | 'thinking' | 'tool' | 'done' | 'error';
  content: string;
  meta?: Record<string, unknown>;
}

// ── Core API Functions ──────────────────────────

const BASE = ''; // Vite proxy forwards to backend

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API Error ${res.status}`);
  }
  return res.json();
}

// ── Health ──────────────────────────────────────

export async function getHealth(): Promise<HealthResponse> {
  return request('/health');
}

// ── Chat (sync) ────────────────────────────────

export async function chatSync(
  message: string,
  conversationId?: string,
  useThinking = true,
): Promise<ChatResponse> {
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      use_thinking: useThinking,
    }),
  });
}

// ── Chat (SSE streaming) ───────────────────────

export async function* chatStream(
  message: string,
  conversationId?: string,
): AsyncGenerator<StreamChunk> {
  const res = await fetch(`${BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      use_thinking: true,
    }),
  });

  if (!res.ok) {
    yield { type: 'error', content: `Stream failed: ${res.statusText}` };
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    yield { type: 'error', content: 'No response body' };
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === 'error') {
            yield { type: 'error', content: data.data || data.message || 'Unknown error' };
          } else if (data.type === 'done' || data.done) {
            yield { type: 'done', content: '', meta: data };
          } else if (data.token || data.content || data.text) {
            yield { type: 'text', content: data.token || data.content || data.text || '' };
          } else if (data.type === 'thinking') {
            yield { type: 'thinking', content: data.step || data.content || '' };
          } else if (data.type === 'tool') {
            yield { type: 'tool', content: data.tool || data.name || '', meta: data };
          }
        } catch {
          // Non-JSON SSE line — treat as raw text
          yield { type: 'text', content: line.slice(6) };
        }
      }
    }
  }
}

// ── Agent Task ─────────────────────────────────

export async function agentTask(
  task: string,
  useThinking = true,
  maxToolCalls = 10,
): Promise<AgentTaskResponse> {
  return request('/agent/task', {
    method: 'POST',
    body: JSON.stringify({
      task,
      use_thinking: useThinking,
      max_tool_calls: maxToolCalls,
    }),
  });
}

// ── Agent Stats ────────────────────────────────

export async function getAgentStats(): Promise<Record<string, unknown>> {
  return request('/agent/stats');
}

// ── Memory ─────────────────────────────────────

export async function getMemoryStats(): Promise<MemoryStatsResponse> {
  return request('/memory/stats');
}

export async function getMemoryFailures(): Promise<{
  count: number;
  failures: unknown[];
}> {
  return request('/memory/failures');
}

export async function memoryRecall(
  query: string,
): Promise<{ query: string; episodes: unknown[]; knowledge_context: string; user_profile: unknown }> {
  return request('/memory/recall', {
    method: 'POST',
    body: JSON.stringify({ query }),
  });
}

// ── Sessions ───────────────────────────────────

export async function getSessions(): Promise<{ sessions: unknown[] }> {
  return request('/sessions');
}

export async function getSessionHistory(
  sessionId: string,
  limit = 50,
): Promise<{ session_id: string; messages: unknown[] }> {
  return request(`/sessions/${sessionId}/history?limit=${limit}`);
}

// ── Processes ──────────────────────────────────

export async function getProcesses(): Promise<{ processes: ProcessInfo[] }> {
  return request('/processes');
}

export async function pollProcess(
  processId: string,
): Promise<Record<string, unknown>> {
  return request(`/processes/${processId}`);
}

// ── Tutor ──────────────────────────────────────

export async function tutorStart(topic: string): Promise<TutorStartResponse> {
  return request('/tutor/start', {
    method: 'POST',
    body: JSON.stringify({ topic }),
  });
}

export async function tutorRespond(
  sessionId: string,
  message: string,
): Promise<TutorRespondResponse> {
  return request('/tutor/respond', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, message }),
  });
}

// ── Swarm Intelligence ─────────────────────────

export async function swarmExecute(
  task: string,
  roles?: string[],
): Promise<SwarmResult> {
  return request('/swarm/execute', {
    method: 'POST',
    body: JSON.stringify({ task, roles }),
  });
}

// ── Tool Forge ─────────────────────────────────

export async function forgeCreateTool(
  description: string,
  name?: string,
): Promise<ForgeResult> {
  return request('/forge/create', {
    method: 'POST',
    body: JSON.stringify({ description, name }),
  });
}

// ── Multimodal Analysis ────────────────────────

export async function multimodalAnalyze(
  filePath: string,
  question?: string,
): Promise<Record<string, unknown>> {
  return request('/analyze', {
    method: 'POST',
    body: JSON.stringify({ file_path: filePath, question }),
  });
}

// ── API Key Management ─────────────────────────

export interface ApiKeySaveResponse {
  status: string;
  activated: number;
  providers: { provider: string; active: boolean }[];
}

export interface ApiKeyStatusResponse {
  providers: { provider: string; active: boolean }[];
  total_active: number;
}

export async function saveApiKeys(keys: string[]): Promise<ApiKeySaveResponse> {
  return request('/api/keys', {
    method: 'POST',
    body: JSON.stringify({ keys }),
  });
}

export async function getApiKeyStatus(): Promise<ApiKeyStatusResponse> {
  return request('/api/keys/status');
}

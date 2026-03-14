/**
 * MCP Client — Direct HTTP connection to the Astra MCP Server.
 * ─────────────────────────────────────────────────────────────
 * Expert-level MCP client with:
 *   • Connection health monitoring with auto-reconnect
 *   • Typed tool invocations for all 24 MCP tools
 *   • Structured error handling with retry logic
 *   • Resource and prompt fetching
 *
 * Usage:
 *   import { mcpClient } from './mcpClient';
 *   const result = await mcpClient.callTool('chat', { message: 'hello' });
 */

// ── Types ────────────────────────────────────────

export interface MCPToolResult {
  success: boolean;
  trace_id?: string;
  timestamp?: string;
  duration_ms?: number;
  data?: Record<string, any>;
  error?: {
    code: string;
    message: string;
    details?: string;
    retry_hint?: string;
  };
  // Legacy flat fields (from original 18 tools)
  [key: string]: any;
}

export interface MCPResourceContent {
  uri: string;
  mimeType: string;
  text: string;
}

export interface MCPCapabilities {
  server: string;
  version: string;
  tools_count: number;
  resources_count: number;
  prompts_count: number;
  tool_categories: Record<string, string[]>;
  transports: string[];
  supported_ides: string[];
}

export interface MCPMetrics {
  uptime_info: string;
  tool_metrics: Record<string, {
    calls: number;
    errors: number;
    avg_latency_ms: number;
    error_rate: number;
  }>;
  circuit_breaker: {
    status: string;
    open_circuits: string[];
  };
}

export interface MCPToolInfo {
  name: string;
  description: string;
  inputSchema?: Record<string, any>;
}

export interface MCPResourceInfo {
  uri: string;
  name: string;
  description?: string;
  mimeType?: string;
}

export interface MCPPromptInfo {
  name: string;
  description?: string;
  arguments?: Array<{
    name: string;
    description?: string;
    required?: boolean;
  }>;
}

export type MCPConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface MCPConnectionState {
  status: MCPConnectionStatus;
  url: string;
  lastCheck: Date | null;
  lastError: string | null;
  serverName: string | null;
  toolsCount: number;
  resourcesCount: number;
  promptsCount: number;
}

// ── Configuration ────────────────────────────────

const MCP_DEFAULT_URL = 'http://127.0.0.1:8080/mcp';
const MCP_TIMEOUT_MS = 60_000;
const MCP_RETRY_COUNT = 2;
const MCP_RETRY_DELAY_MS = 1000;
const MCP_HEALTH_INTERVAL_MS = 30_000;

// ── MCP HTTP Client ──────────────────────────────

class MCPClient {
  private _url: string;
  private _state: MCPConnectionState;
  private _healthInterval: ReturnType<typeof setInterval> | null = null;
  private _listeners: Set<(state: MCPConnectionState) => void> = new Set();
  private _cachedTools: MCPToolInfo[] | null = null;
  private _cachedResources: MCPResourceInfo[] | null = null;
  private _cachedPrompts: MCPPromptInfo[] | null = null;

  constructor(url?: string) {
    this._url = url || MCP_DEFAULT_URL;
    this._state = {
      status: 'disconnected',
      url: this._url,
      lastCheck: null,
      lastError: null,
      serverName: null,
      toolsCount: 0,
      resourcesCount: 0,
      promptsCount: 0,
    };
  }

  // ── State Management ──

  get state(): MCPConnectionState {
    return { ...this._state };
  }

  get isConnected(): boolean {
    return this._state.status === 'connected';
  }

  get url(): string {
    return this._url;
  }

  setUrl(url: string): void {
    this._url = url;
    this._state.url = url;
    this._cachedTools = null;
    this._cachedResources = null;
    this._cachedPrompts = null;
    this._updateState({ status: 'disconnected', lastError: null });
  }

  subscribe(listener: (state: MCPConnectionState) => void): () => void {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  private _updateState(partial: Partial<MCPConnectionState>): void {
    this._state = { ...this._state, ...partial };
    this._listeners.forEach(fn => {
      try { fn(this._state); } catch { /* swallow listener errors */ }
    });
  }

  // ── Connection Management ──

  async connect(): Promise<boolean> {
    this._updateState({ status: 'connecting', lastError: null });
    try {
      // Use initialize or list tools to check connection
      const tools = await this._rpcCall<{ tools: MCPToolInfo[] }>('tools/list', {});
      const resources = await this._rpcCall<{ resources: MCPResourceInfo[] }>('resources/list', {});
      const prompts = await this._rpcCall<{ prompts: MCPPromptInfo[] }>('prompts/list', {});

      this._cachedTools = tools.tools || [];
      this._cachedResources = resources.resources || [];
      this._cachedPrompts = prompts.prompts || [];

      this._updateState({
        status: 'connected',
        lastCheck: new Date(),
        lastError: null,
        serverName: 'Astra SuperChain AI Agent',
        toolsCount: this._cachedTools.length,
        resourcesCount: this._cachedResources.length,
        promptsCount: this._cachedPrompts.length,
      });

      return true;
    } catch (err: any) {
      this._updateState({
        status: 'error',
        lastCheck: new Date(),
        lastError: err.message || 'Connection failed',
      });
      return false;
    }
  }

  async disconnect(): Promise<void> {
    this.stopHealthCheck();
    this._cachedTools = null;
    this._cachedResources = null;
    this._cachedPrompts = null;
    this._updateState({
      status: 'disconnected',
      lastError: null,
      serverName: null,
      toolsCount: 0,
      resourcesCount: 0,
      promptsCount: 0,
    });
  }

  startHealthCheck(): void {
    this.stopHealthCheck();
    this._healthInterval = setInterval(async () => {
      if (this._state.status === 'connected' || this._state.status === 'error') {
        try {
          await this._rpcCall('tools/list', {});
          if (this._state.status !== 'connected') {
            this._updateState({ status: 'connected', lastError: null, lastCheck: new Date() });
          } else {
            this._updateState({ lastCheck: new Date() });
          }
        } catch {
          this._updateState({ status: 'error', lastCheck: new Date(), lastError: 'Health check failed' });
        }
      }
    }, MCP_HEALTH_INTERVAL_MS);
  }

  stopHealthCheck(): void {
    if (this._healthInterval) {
      clearInterval(this._healthInterval);
      this._healthInterval = null;
    }
  }

  // ── Tool Invocation ──

  async callTool(name: string, args: Record<string, any> = {}): Promise<MCPToolResult> {
    try {
      const result = await this._rpcCall<{ content: Array<{ type: string; text?: string }> }>(
        'tools/call',
        { name, arguments: args },
      );

      // Parse the text content from MCP response
      const textContent = result.content?.find(c => c.type === 'text');
      if (textContent?.text) {
        try {
          return JSON.parse(textContent.text);
        } catch {
          return { success: true, data: { raw: textContent.text } };
        }
      }

      return { success: true, data: result as any };
    } catch (err: any) {
      return {
        success: false,
        error: {
          code: 'CLIENT_ERROR',
          message: err.message || 'Tool call failed',
          retry_hint: 'Check MCP server is running',
        },
      };
    }
  }

  // ── Resource Reading ──

  async readResource(uri: string): Promise<string | null> {
    try {
      const result = await this._rpcCall<{ contents: MCPResourceContent[] }>(
        'resources/read',
        { uri },
      );
      return result.contents?.[0]?.text || null;
    } catch {
      return null;
    }
  }

  // ── Cached Listings ──

  async listTools(refresh = false): Promise<MCPToolInfo[]> {
    if (this._cachedTools && !refresh) return this._cachedTools;
    try {
      const result = await this._rpcCall<{ tools: MCPToolInfo[] }>('tools/list', {});
      this._cachedTools = result.tools || [];
      return this._cachedTools;
    } catch {
      return this._cachedTools || [];
    }
  }

  async listResources(refresh = false): Promise<MCPResourceInfo[]> {
    if (this._cachedResources && !refresh) return this._cachedResources;
    try {
      const result = await this._rpcCall<{ resources: MCPResourceInfo[] }>('resources/list', {});
      this._cachedResources = result.resources || [];
      return this._cachedResources;
    } catch {
      return this._cachedResources || [];
    }
  }

  async listPrompts(refresh = false): Promise<MCPPromptInfo[]> {
    if (this._cachedPrompts && !refresh) return this._cachedPrompts;
    try {
      const result = await this._rpcCall<{ prompts: MCPPromptInfo[] }>('prompts/list', {});
      this._cachedPrompts = result.prompts || [];
      return this._cachedPrompts;
    } catch {
      return this._cachedPrompts || [];
    }
  }

  // ── Convenience Methods for Key Resources ──

  async getCapabilities(): Promise<MCPCapabilities | null> {
    const text = await this.readResource('system://capabilities');
    if (!text) return null;
    try { return JSON.parse(text); } catch { return null; }
  }

  async getMetrics(): Promise<MCPMetrics | null> {
    const text = await this.readResource('system://metrics');
    if (!text) return null;
    try { return JSON.parse(text); } catch { return null; }
  }

  async getHealth(): Promise<Record<string, any> | null> {
    const text = await this.readResource('system://health');
    if (!text) return null;
    try { return JSON.parse(text); } catch { return null; }
  }

  // ── Internal RPC ──

  private async _rpcCall<T = any>(method: string, params: Record<string, any>): Promise<T> {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= MCP_RETRY_COUNT; attempt++) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), MCP_TIMEOUT_MS);

      try {
        const body = {
          jsonrpc: '2.0',
          id: Date.now() + Math.random(),
          method,
          params,
        };

        const res = await fetch(this._url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/event-stream',
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!res.ok) {
          const errorText = await res.text().catch(() => `HTTP ${res.status}`);
          throw new Error(`MCP server error (${res.status}): ${errorText.slice(0, 200)}`);
        }

        const contentType = res.headers.get('content-type') || '';

        // Handle SSE streaming responses
        if (contentType.includes('text/event-stream')) {
          return await this._parseSSE<T>(res);
        }

        // Handle regular JSON
        const json = await res.json();

        if (json.error) {
          throw new Error(json.error.message || JSON.stringify(json.error));
        }

        return json.result as T;
      } catch (err: any) {
        clearTimeout(timeoutId);
        lastError = err;

        const isRetryable = err.name === 'AbortError' ||
          err.message?.includes('Failed to fetch') ||
          err.message?.includes('NetworkError') ||
          err.message?.includes('5');

        if (isRetryable && attempt < MCP_RETRY_COUNT) {
          await new Promise(r => setTimeout(r, MCP_RETRY_DELAY_MS * (attempt + 1)));
          continue;
        }

        throw err;
      }
    }

    throw lastError || new Error('RPC call failed');
  }

  private async _parseSSE<T>(res: Response): Promise<T> {
    const reader = res.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';
    let result: any = null;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data) {
              try {
                const parsed = JSON.parse(data);
                if (parsed.result) result = parsed.result;
                if (parsed.error) throw new Error(parsed.error.message || 'SSE error');
              } catch (e: any) {
                if (e.message?.includes('SSE error')) throw e;
                // Skip non-JSON data lines
              }
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    if (!result) throw new Error('No result in SSE stream');
    return result as T;
  }
}

// ── Singleton Export ──────────────────────────────

export const mcpClient = new MCPClient();
export default mcpClient;

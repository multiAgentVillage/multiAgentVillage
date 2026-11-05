import { ApiError, apiRequest } from './client';

export type RunStatus = 'DRAFT' | 'READY' | 'RUNNING' | 'PAUSED' | 'FINISHED' | 'FAILED';
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface RunSummary {
  run_id: string;
  name: string;
  status: RunStatus;
  sim_time_ms: number;
  last_seq: number;
}

export interface AgentSummary {
  agent_id: string;
  name: string;
  location_id: string | null;
  location_name: string | null;
}

export interface RunState extends RunSummary {
  agents: AgentSummary[];
  locations: { location_id: string; name: string; is_open: boolean }[];
}

export interface DomainEvent {
  event_id: string;
  run_id: string;
  seq: number;
  type: string;
  schema_version: number;
  sim_time_ms: number;
  occurred_at: string;
  correlation_id: string;
  causation_id: string;
  payload: { [key: string]: JsonValue };
}

export interface EventPage {
  items: DomainEvent[];
  next_seq: number;
  has_more: boolean;
}

export interface NoticeRequest {
  request_id: string;
  type: 'PublishNotice';
  schema_version: 1;
  payload: { content: string; recipient_agent_ids: string[] };
}

export interface CommandReceipt {
  command_id: string;
  status: 'accepted' | 'pending' | 'deferred' | 'applied' | 'rejected';
  result_event_ids: string[];
  reason: string | null;
}

export interface Memory {
  memory_id: string;
  source_event_id: string;
  content: string;
  sim_time_ms: number;
}

export interface AgentDetail {
  agent_id: string;
  name: string;
  location_id: string | null;
  memories: Memory[];
}

async function jsonRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const timeout = AbortSignal.timeout(10_000);
  const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
  const response = await apiRequest(path, { ...init, signal });
  if (!response.ok) {
    let detail = `请求失败（HTTP ${response.status}）`;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === 'object' && 'detail' in body) {
        if (typeof body.detail === 'string') detail = body.detail;
        else if (Array.isArray(body.detail)) detail = '提交内容不符合要求，请检查后重试。';
      }
    } catch { /* Preserve the HTTP status when the proxy sends a non-JSON error. */ }
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

const runPath = (runId: string) => `/runs/${encodeURIComponent(runId)}`;

export const listRuns = (signal?: AbortSignal) =>
  jsonRequest<{ items: RunSummary[] }>('/runs', { signal });
export const getRunState = (runId: string, signal?: AbortSignal) =>
  jsonRequest<RunState>(`${runPath(runId)}/state`, { signal });
export const listEvents = (runId: string, afterSeq: number, signal?: AbortSignal) =>
  jsonRequest<EventPage>(`${runPath(runId)}/events?after_seq=${afterSeq}&limit=100`, { signal });
export const publishNotice = (runId: string, request: NoticeRequest) =>
  jsonRequest<CommandReceipt>(`${runPath(runId)}/commands`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request),
  });
export const getCommand = (runId: string, commandId: string, signal?: AbortSignal) =>
  jsonRequest<CommandReceipt>(`${runPath(runId)}/commands/${encodeURIComponent(commandId)}`, { signal });
export const getAgent = (runId: string, agentId: string, signal?: AbortSignal) =>
  jsonRequest<AgentDetail>(`${runPath(runId)}/agents/${encodeURIComponent(agentId)}`, { signal });

import { ApiError, apiRequest } from './client';

export type DependencyStatus = 'ok' | 'unavailable';

export interface ReadinessReport {
  status: 'ready' | 'not_ready';
  dependencies: {
    postgres: DependencyStatus;
    redis: DependencyStatus;
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isDependencyStatus(value: unknown): value is DependencyStatus {
  return value === 'ok' || value === 'unavailable';
}

function isReadinessReport(value: unknown): value is ReadinessReport {
  if (!isRecord(value) || !isRecord(value.dependencies)) return false;
  return (
    (value.status === 'ready' || value.status === 'not_ready') &&
    isDependencyStatus(value.dependencies.postgres) &&
    isDependencyStatus(value.dependencies.redis)
  );
}

export async function getReadiness(signal?: AbortSignal): Promise<ReadinessReport> {
  const response = await apiRequest('/health/ready', { signal });
  // 503 carries a real dependency report; display it instead of inventing success.
  if (!response.ok && response.status !== 503) {
    throw new ApiError(`健康检查失败（HTTP ${response.status}）`, response.status);
  }
  const payload: unknown = await response.json();
  if (!isReadinessReport(payload)) throw new ApiError('健康检查响应格式不符合约定');
  return payload;
}

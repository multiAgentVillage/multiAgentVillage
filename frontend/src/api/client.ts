/** Browser requests always use the same origin; dev/nginx proxies reach api. */
export const API_PREFIX = '/api';

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiRequest(path: string, init?: RequestInit): Promise<Response> {
  if (!path.startsWith('/')) throw new ApiError('API path must start with /');
  const headers = new Headers(init?.headers);
  if (!headers.has('Accept')) headers.set('Accept', 'application/json');
  return fetch(`${API_PREFIX}${path}`, {
    ...init,
    headers,
  });
}

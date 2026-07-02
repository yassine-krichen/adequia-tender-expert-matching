const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type ApiResult<T> = { data: T; error: null } | { data: null; error: string };

async function request<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, init);

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      return { data: null, error: body?.message ?? `Request failed (${response.status})` };
    }

    return { data: (await response.json()) as T, error: null };
  } catch {
    return { data: null, error: 'Network error' };
  }
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    }),
  // No Content-Type header here — the browser sets the multipart boundary
  // itself when the body is a FormData instance.
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: 'POST', body: formData }),
};

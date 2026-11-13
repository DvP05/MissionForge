import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];

export type ApiError = Schemas["ApiError"];
export type ApiMeta = Schemas["ApiMeta"];

/** Generic response envelope; mirrors backend `ApiResult[T]` (see schema.d.ts). */
export interface ApiResult<T> {
  ok: boolean;
  data: T | null;
  error: ApiError | null;
  meta: ApiMeta;
}

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function networkError<T>(message: string): ApiResult<T> {
  return {
    ok: false,
    data: null,
    error: { code: "NETWORK_ERROR", message, retryable: true },
    meta: { requestId: "client", schemaVersion: "1.0" },
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, init);
    return (await response.json()) as ApiResult<T>;
  } catch (cause) {
    const message =
      cause instanceof Error ? cause.message : "Unable to reach the MISSIONFORGE backend.";
    return networkError<T>(message);
  }
}

export function apiGet<T>(path: string, init?: RequestInit): Promise<ApiResult<T>> {
  return request<T>(path, { ...init, method: "GET" });
}

export function apiPost<T, B = unknown>(
  path: string,
  body: B,
  init?: RequestInit,
): Promise<ApiResult<T>> {
  return request<T>(path, {
    ...init,
    method: "POST",
    headers: { "Content-Type": "application/json", ...init?.headers },
    body: JSON.stringify(body),
  });
}

import type { components, paths } from "@/lib/api/schema";

type Schemas = components["schemas"];

export type ApiError = Schemas["ApiError"];
export type ApiMeta = Schemas["ApiMeta"];

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export const DEFAULT_TIMEOUT_MS = 10_000;

// ---- Path-keyed typing derived from the generated OpenAPI `paths` type ----

type JsonBody<T> = T extends { content: { "application/json": infer B } } ? B : never;

type GetPath = {
  [P in keyof paths]: paths[P] extends { get: object } ? P : never;
}[keyof paths];

type PostPath = {
  [P in keyof paths]: paths[P] extends { post: object } ? P : never;
}[keyof paths];

type GetOp<P extends GetPath> = paths[P] extends { get: infer O } ? O : never;
type PostOp<P extends PostPath> = paths[P] extends { post: infer O } ? O : never;

type OkResponse<Op> = Op extends { responses: { 200: infer R } } ? JsonBody<R> : never;

type PathParamsOf<Op> = Op extends { parameters: { path: infer X } } ? X : never;
type QueryOf<Op> = Op extends { parameters: { query?: infer Q } } ? Q : never;

type CommonOptions = {
  /** Caller cancellation (e.g. stale revision, unmount). */
  signal?: AbortSignal;
  /** Overrides DEFAULT_TIMEOUT_MS. */
  timeoutMs?: number;
};

export type GetOptions<P extends GetPath> = CommonOptions &
  ([PathParamsOf<GetOp<P>>] extends [never]
    ? { pathParams?: undefined }
    : { pathParams: PathParamsOf<GetOp<P>> }) &
  ([QueryOf<GetOp<P>>] extends [never] ? object : { query?: QueryOf<GetOp<P>> });

type RequestBodyOf<Op> = Op extends { requestBody: { content: { "application/json": infer B } } }
  ? B
  : never;

/** Server envelope plus the HTTP status (null when no response was received). */
export type ApiResponse<R> = R & { httpStatus: number | null };

/** Data payload type of an endpoint's envelope. */
export type DataOf<R> = R extends { data?: infer D } ? NonNullable<D> : never;

// ---- Transport ----

type Envelope = {
  ok: boolean;
  data: unknown;
  error: ApiError | null;
  meta: ApiMeta;
};

function failure(
  code: string,
  message: string,
  retryable: boolean,
  httpStatus: number | null,
): Envelope & { httpStatus: number | null } {
  return {
    ok: false,
    data: null,
    error: { code, message, retryable },
    meta: { requestId: "client", schemaVersion: "1.0" },
    httpStatus,
  };
}

function isEnvelope(value: unknown): value is Envelope {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Envelope).ok === "boolean" &&
    typeof (value as Envelope).meta === "object"
  );
}

function buildUrl(
  template: string,
  pathParams: Record<string, unknown> | undefined,
  query: Record<string, unknown> | undefined,
): string {
  let path = template;
  for (const [key, value] of Object.entries(pathParams ?? {})) {
    path = path.replace(`{${key}}`, encodeURIComponent(String(value)));
  }
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null) search.set(key, String(value));
  }
  const qs = search.toString();
  return `${API_BASE_URL}${path}${qs ? `?${qs}` : ""}`;
}

async function request(
  url: string,
  init: RequestInit,
  options: CommonOptions,
): Promise<Envelope & { httpStatus: number | null }> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const external = options.signal;
  const onExternalAbort = () => controller.abort();
  if (external) {
    if (external.aborted) controller.abort();
    else external.addEventListener("abort", onExternalAbort, { once: true });
  }

  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    let body: unknown;
    try {
      body = await response.json();
    } catch (cause) {
      if (controller.signal.aborted) throw cause;
      return failure(
        "NON_JSON_RESPONSE",
        `The backend returned a non-JSON response (HTTP ${response.status}).`,
        response.status >= 500,
        response.status,
      );
    }
    if (!isEnvelope(body)) {
      return failure(
        "UNEXPECTED_RESPONSE",
        `The backend returned an unexpected response shape (HTTP ${response.status}).`,
        response.status >= 500,
        response.status,
      );
    }
    return { ...body, httpStatus: response.status };
  } catch (cause) {
    if (timedOut) {
      return failure("TIMEOUT", "The backend did not respond in time.", true, null);
    }
    if (external?.aborted) {
      return failure("ABORTED", "The request was cancelled.", false, null);
    }
    const message =
      cause instanceof Error ? cause.message : "Unable to reach the MISSIONFORGE backend.";
    return failure("NETWORK_ERROR", message, true, null);
  } finally {
    clearTimeout(timer);
    external?.removeEventListener("abort", onExternalAbort);
  }
}

export function apiGet<P extends GetPath>(
  path: P,
  ...[options]: [GetOptions<P>] extends [CommonOptions & { pathParams?: undefined }]
    ? [options?: GetOptions<P>]
    : [options: GetOptions<P>]
): Promise<ApiResponse<OkResponse<GetOp<P>>>> {
  const opts = (options ?? {}) as CommonOptions & {
    pathParams?: Record<string, unknown>;
    query?: Record<string, unknown>;
  };
  return request(
    buildUrl(path, opts.pathParams, opts.query),
    { method: "GET" },
    opts,
  ) as unknown as Promise<ApiResponse<OkResponse<GetOp<P>>>>;
}

export function apiPost<P extends PostPath>(
  path: P,
  body: RequestBodyOf<PostOp<P>>,
  options: CommonOptions & { pathParams?: Record<string, unknown> } = {},
): Promise<ApiResponse<OkResponse<PostOp<P>>>> {
  return request(
    buildUrl(path, options.pathParams, undefined),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    options,
  ) as unknown as Promise<ApiResponse<OkResponse<PostOp<P>>>>;
}

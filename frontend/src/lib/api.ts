/**
 * The ONE place the frontend talks to the backend.
 *
 * `api-types.ts` is generated from the backend's OpenAPI schema (`npm run gen:api`),
 * so every path, parameter, and response field below is type-checked. If the backend
 * renames a field, TypeScript points at every line that breaks.
 */
import createClient from "openapi-fetch";

import type { components, paths } from "./api-types";
import { API_URL } from "./config";

export type Schemas = components["schemas"];

export const api = createClient<paths>({ baseUrl: API_URL });

/** An error with a message written for the person using the app. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number, // 0 = the request never reached the server
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiResult<T> = { data?: T; error?: unknown; response: Response };

function messageFrom(error: unknown, status: number): string {
  // FastAPI errors look like {"detail": "..."} or {"detail": [{"msg": "..."}, ...]}.
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  if (status === 503) return "This feature isn't configured on the server yet.";
  if (status >= 500) return "The server had a problem. Try again in a moment.";
  return `Request failed (HTTP ${status}).`;
}

/** Turns an openapi-fetch result into data, or throws an ApiError with a clear message. */
export async function unwrap<T>(request: Promise<ApiResult<T>>): Promise<T> {
  let result: ApiResult<T>;
  try {
    result = await request;
  } catch {
    throw new ApiError(
      `Can't reach the Capital Insight API at ${API_URL}. Start the backend with: uvicorn app.main:app --reload`,
      0,
    );
  }
  if (result.data === undefined) {
    throw new ApiError(messageFrom(result.error, result.response.status), result.response.status);
  }
  return result.data;
}

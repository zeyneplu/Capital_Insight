import "server-only";
import { authToken, coreRequest } from "@/lib/auth";
import type { PlanningOverview, SamTurn } from "@/lib/planning-types";

/**
 * Planning, goals and Sam live only in the core API (they persist per verified user),
 * so fixture mode explains the requirement instead of inventing saved goals.
 */
export type PlanningLoad<T> =
  | { status: "ok"; data: T }
  | { status: "unconfigured" }
  | { status: "signed-out" }
  | { status: "error"; message: string };

export function planningConfigured(): boolean {
  return Boolean(process.env.BACKEND_API_URL);
}

async function load<T>(path: string): Promise<PlanningLoad<T>> {
  // Read the request cookie first so this never prerenders with build-time configuration.
  const token = await authToken();
  if (!planningConfigured()) return { status: "unconfigured" };
  if (!token) return { status: "signed-out" };
  try {
    const response = await coreRequest("/v1/planning" + path, { token });
    if (response.status === 401 || response.status === 403) return { status: "signed-out" };
    if (!response.ok) return { status: "error", message: "Your planning data could not be loaded. Try again shortly." };
    return { status: "ok", data: (await response.json()) as T };
  } catch {
    return { status: "error", message: "The Capital Insight API is unavailable. Check that the core backend is running." };
  }
}

export const loadPlanningOverview = () => load<PlanningOverview>("/overview");
export const loadSamHistory = () => load<SamTurn[]>("/sam/history");

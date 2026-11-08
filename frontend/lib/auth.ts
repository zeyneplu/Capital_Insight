import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export const AUTH_COOKIE = "ci_auth";
export const ADAPTER_COOKIE = "ci_backend_session";
export interface AppUser { id: string; email: string; email_verified_at: string | null; created_at: string }

export async function coreRequest(path: string, init: { method?: string; body?: unknown; token?: string } = {}) {
  const base = process.env.BACKEND_API_URL;
  if (!base) throw new Error("Set BACKEND_API_URL to use email sign-in.");
  return fetch(base.replace(/\/$/, "") + path, {
    method: init.method ?? "GET", cache: "no-store",
    headers: { "Content-Type":"application/json", ...(init.token ? {Authorization:`Bearer ${init.token}`} : {}) },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
}

export async function authToken() { return (await cookies()).get(AUTH_COOKIE)?.value; }
export async function currentAppUser(): Promise<AppUser | null> {
  const token = await authToken();
  if (!token) return null;
  const response = await coreRequest("/v1/auth/me", {token});
  if (response.status === 401) return null;
  if (!response.ok) throw new Error("Could not load your account. Try again.");
  return response.json();
}
export async function requireVerifiedUser() {
  const user = await currentAppUser();
  if (!user?.email_verified_at) redirect("/sign-in");
  return user;
}

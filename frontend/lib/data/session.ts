import "server-only";
import { cookies } from "next/headers";
import { cache } from "react";
import { validateLoanApplication, validateMortgageApplication, type LoanApplicationInput, type MortgageApplicationInput } from "@/lib/finance/underwriting";
import { DEFAULT_CONNECTIONS, INSTITUTIONS } from "./fixtures/institutions";
import { LOAN_TYPES } from "@/lib/types";

/**
 * Session-local demo state for fixture mode.
 *
 * Persistence limits (also shown in the UI):
 *  - Stored in one httpOnly cookie in this browser only, for up to 7 days.
 *  - Keeps the 5 most recent simulated applications per lender.
 *  - Cleared by "Reset demo" or by clearing site cookies.
 *
 * The cookie is user-controlled input, so every field is validated on read and
 * application decisions are re-derived from the stored inputs, never trusted.
 */
const COOKIE_NAME = "ci_demo_session";
const MAX_AGE_SECONDS = 60 * 60 * 24 * 7;
const MAX_APPLICATIONS = 5;
const MAX_COOKIE_BYTES = 3800;

export interface StoredConsent {
  institutionId: string;
  email: string;
  requestedAt: string;
  attempts: number;
}

export interface StoredLoanApplication extends LoanApplicationInput {
  id: string;
  created_at: string;
}

export interface StoredMortgageApplication extends MortgageApplicationInput {
  id: string;
  created_at: string;
}

export interface DemoSession {
  v: 1;
  connections: string[];
  consent: StoredConsent | null;
  loanApplications: StoredLoanApplication[];
  mortgageApplications: StoredMortgageApplication[];
}

const KNOWN_INSTITUTIONS = new Set(INSTITUTIONS.map((institution) => institution.id));

export function defaultSession(): DemoSession {
  return { v: 1, connections: [...DEFAULT_CONNECTIONS], consent: null, loanApplications: [], mortgageApplications: [] };
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const isTimestamp = (value: unknown): value is string => typeof value === "string" && value.length <= 40 && !Number.isNaN(Date.parse(value));
const isId = (value: unknown): value is string => typeof value === "string" && /^[A-Za-z0-9-]{1,64}$/.test(value);
const asForm = (value: Record<string, unknown>) =>
  Object.fromEntries(Object.entries(value).map(([key, item]) => [key, typeof item === "string" || typeof item === "number" ? String(item) : undefined]));

function parseLoan(value: unknown): StoredLoanApplication | null {
  if (!isRecord(value) || !isId(value.id) || !isTimestamp(value.created_at)) return null;
  const validated = validateLoanApplication(asForm(value), LOAN_TYPES);
  return validated.ok ? { ...validated.value, id: value.id, created_at: value.created_at } : null;
}

function parseMortgage(value: unknown): StoredMortgageApplication | null {
  if (!isRecord(value) || !isId(value.id) || !isTimestamp(value.created_at)) return null;
  const validated = validateMortgageApplication(asForm(value));
  return validated.ok ? { ...validated.value, id: value.id, created_at: value.created_at } : null;
}

function parseConsent(value: unknown): StoredConsent | null {
  if (!isRecord(value)) return null;
  const { institutionId, email, requestedAt, attempts } = value;
  if (typeof institutionId !== "string" || !KNOWN_INSTITUTIONS.has(institutionId)) return null;
  if (typeof email !== "string" || email.length > 254 || !isTimestamp(requestedAt)) return null;
  if (typeof attempts !== "number" || !Number.isInteger(attempts) || attempts < 0) return null;
  return { institutionId, email, requestedAt, attempts };
}

export function decodeSession(encoded: string | undefined): DemoSession {
  if (!encoded) return defaultSession();
  try {
    const value: unknown = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
    if (!isRecord(value) || value.v !== 1 || !Array.isArray(value.connections)) return defaultSession();
    const keep = <T>(items: unknown, parse: (item: unknown) => T | null): T[] =>
      Array.isArray(items) ? items.map(parse).filter((item): item is T => item !== null).slice(0, MAX_APPLICATIONS) : [];
    return {
      v: 1,
      connections: [...new Set(value.connections.filter((id): id is string => typeof id === "string" && KNOWN_INSTITUTIONS.has(id)))],
      consent: parseConsent(value.consent),
      loanApplications: keep(value.loanApplications, parseLoan),
      mortgageApplications: keep(value.mortgageApplications, parseMortgage),
    };
  } catch {
    return defaultSession();
  }
}

export function encodeSession(session: DemoSession): string {
  const trimmed: DemoSession = {
    ...session,
    loanApplications: session.loanApplications.slice(0, MAX_APPLICATIONS),
    mortgageApplications: session.mortgageApplications.slice(0, MAX_APPLICATIONS),
  };
  let encoded = Buffer.from(JSON.stringify(trimmed), "utf8").toString("base64url");
  // Stay under the browser's ~4 KB cookie limit by dropping the oldest applications.
  while (encoded.length > MAX_COOKIE_BYTES && (trimmed.loanApplications.length || trimmed.mortgageApplications.length)) {
    if (trimmed.loanApplications.length >= trimmed.mortgageApplications.length) trimmed.loanApplications.pop();
    else trimmed.mortgageApplications.pop();
    encoded = Buffer.from(JSON.stringify(trimmed), "utf8").toString("base64url");
  }
  return encoded;
}

/** Reads the session once per request (React `cache` deduplicates calls). */
export const readSession = cache(async (): Promise<DemoSession> => {
  const store = await cookies();
  return decodeSession(store.get(COOKIE_NAME)?.value);
});

/** Only callable from Server Actions or Route Handlers, where cookies can be set. */
export async function writeSession(session: DemoSession): Promise<void> {
  const store = await cookies();
  store.set(COOKIE_NAME, encodeSession(session), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
}

export async function clearSession(): Promise<void> {
  const store = await cookies();
  store.delete(COOKIE_NAME);
}

export const SESSION_LIMITS = { maxApplications: MAX_APPLICATIONS, maxAgeDays: MAX_AGE_SECONDS / 86_400 } as const;

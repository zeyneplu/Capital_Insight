import "server-only";
import { cookies } from "next/headers";
import { buildSampleInsights } from "@/lib/finance/insights";
import { buildDashboard } from "@/lib/finance/portfolio";
import { validateLoanApplication, validateMortgageApplication, type FieldError } from "@/lib/finance/underwriting";
import type {
  Account,
  ConnectableInstitution,
  InstitutionSummary,
  LoanApplication,
  MortgageApplication,
  RawAccount,
  RawCustomer,
  RawInstallment,
  RawLoanApplication,
  RawLoanOffer,
  RawMortgageApplication,
  RawMortgageOffer,
  RawTransaction,
  RawTransactionPage,
  ScheduleResult,
  ServiceKind,
} from "@/lib/types";
import { LOAN_TYPES } from "@/lib/types";
import { INSTITUTIONS } from "./fixtures/institutions";
import { normalizeAccount, normalizeLoanApplication, normalizeLoanOffer, normalizeMortgageApplication, normalizeTransaction } from "./normalize";
import { DataSourceUnavailableError, type DataProvider, type Gated, type SubmitResult } from "./provider";

/**
 * Talks to the Capital Insight core API (backend/). The browser never sees bank
 * tokens: this server keeps only an opaque backend session id in an httpOnly
 * cookie. Failures throw (error page) and never fall back to fixtures.
 */
const SESSION_COOKIE = "ci_backend_session";

interface BackendInstitution {
  id: string;
  name: string;
  service: ServiceKind;
  connected: boolean;
  customer: RawCustomer | null;
}

class ApiResponse {
  constructor(
    readonly status: number,
    readonly body: unknown,
    readonly headers: Headers,
  ) {}
}

function baseUrl(): string {
  const url = process.env.BACKEND_API_URL;
  if (!url) throw new DataSourceUnavailableError("DATA_SOURCE=http needs BACKEND_API_URL (for example http://localhost:8000).");
  return url.replace(/\/$/, "");
}

async function request(path: string, init: { method?: string; body?: unknown; sessionId?: string } = {}): Promise<ApiResponse> {
  let response: Response;
  try {
    response = await fetch(baseUrl() + path, {
      method: init.method ?? "GET",
      headers: { "Content-Type": "application/json", ...(init.sessionId ? { "X-Session-Id": init.sessionId } : {}) },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      cache: "no-store", // customer-specific: never in a shared cache
    });
  } catch {
    throw new DataSourceUnavailableError(`The Capital Insight backend at ${baseUrl()} is unreachable.`);
  }
  const text = await response.text();
  return new ApiResponse(response.status, text ? JSON.parse(text) : null, response.headers);
}

/** Throws for anything other than the expected statuses. */
function expect<T>(response: ApiResponse, ...ok: number[]): T {
  if (!ok.includes(response.status)) {
    throw new DataSourceUnavailableError(`Backend answered ${response.status}: ${JSON.stringify(response.body).slice(0, 200)}`);
  }
  return response.body as T;
}

/** FastAPI `detail` can be a string, an object we tag, or a 422 array of {loc, msg}. */
function detailOf(body: unknown): { message: string; errors: FieldError[] } {
  const detail = (body as { detail?: unknown })?.detail;
  const inner = typeof detail === "object" && detail !== null && "detail" in detail ? (detail as { detail: unknown }).detail : detail;
  if (Array.isArray(inner)) {
    const errors = inner.map((item: { loc?: unknown[]; msg?: string }) => ({
      field: typeof item.loc?.at(-1) === "string" ? String(item.loc.at(-1)) : null,
      message: String(item.msg ?? "Invalid value"),
    }));
    return { message: errors.map((e) => e.message).join(" "), errors };
  }
  const message = typeof inner === "string" ? inner : "The request was rejected.";
  return { message, errors: [{ field: null, message }] };
}

async function readSessionId(): Promise<string | undefined> {
  return (await cookies()).get(SESSION_COOKIE)?.value;
}

/** Only from Server Actions: creates a backend session when there is none (or it expired). */
async function ensureSessionId(): Promise<string> {
  const existing = await readSessionId();
  if (existing && (await request("/api/v1/institutions", { sessionId: existing })).status === 200) return existing;
  const { session_id } = expect<{ session_id: string }>(await request("/api/v1/sessions", { method: "POST" }), 201);
  (await cookies()).set(SESSION_COOKIE, session_id, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/" });
  return session_id;
}

function metadata(institution: Pick<BackendInstitution, "id" | "name" | "service">): ConnectableInstitution {
  const known = INSTITUTIONS.find((candidate) => candidate.id === institution.id);
  return {
    id: institution.id,
    name: institution.name,
    service: institution.service,
    shortName: known?.shortName ?? institution.name,
    description: known?.description ?? "",
    products: known?.products ?? [],
    demoEmail: known?.demoEmail ?? "",
    defaultPort: known?.defaultPort ?? 0,
  };
}

/** Institutions with this session's status. Without a session, everything is disconnected. */
async function institutions(): Promise<{ sessionId?: string; items: BackendInstitution[] }> {
  const sessionId = await readSessionId();
  if (sessionId) {
    const response = await request("/api/v1/institutions", { sessionId });
    if (response.status === 200) return { sessionId, items: response.body as BackendInstitution[] };
    if (response.status !== 401) expect(response, 200);
  }
  // No (or expired) session: list institutions as disconnected using known metadata.
  return { items: INSTITUTIONS.map((i) => ({ id: i.id, name: i.name, service: i.service, connected: false, customer: null })) };
}

const summaryOf = (i: Pick<BackendInstitution, "id" | "name" | "service">): InstitutionSummary => ({ id: i.id, name: i.name, service: i.service });

/** Partial results are an error here: we never show a silently incomplete picture. */
function complete<T>(body: { items: T[]; errors: { institution_id: string; status: number }[] }): T[] {
  if (body.errors.length) {
    const reconnect = body.errors.filter((e) => e.status === 401).map((e) => e.institution_id);
    throw new DataSourceUnavailableError(
      reconnect.length
        ? `Consent expired for ${reconnect.join(", ")}. Reconnect on the Connections page.`
        : `Could not load data from ${body.errors.map((e) => e.institution_id).join(", ")}.`,
    );
  }
  return body.items;
}

async function loadAccounts(type?: string): Promise<{ accounts: Account[]; context: Awaited<ReturnType<typeof institutions>> }> {
  const context = await institutions();
  if (!context.sessionId || !context.items.some((i) => i.connected && i.service === "mock_bank")) return { accounts: [], context };
  const query = type ? `?account_type=${encodeURIComponent(type)}` : "";
  const raw = complete(expect<{ items: RawAccount[]; errors: [] }>(await request(`/api/v1/accounts${query}`, { sessionId: context.sessionId }), 200));
  const byId = new Map(context.items.map((i) => [i.id, summaryOf(i)]));
  return { accounts: raw.filter((a) => byId.has(a.institution_id)).map((a) => normalizeAccount(a, byId.get(a.institution_id)!)), context };
}

type LenderId = "loans" | "mortgages";

async function lenderApplications(lenderId: LenderId): Promise<Gated<(LoanApplication | MortgageApplication)[]>> {
  const context = await institutions();
  const lender = context.items.find((i) => i.id === lenderId)!;
  const institution = metadata(lender);
  if (!context.sessionId || !lender.connected) return { connected: false, institution };
  const body = expect<{ connected: boolean; items: (RawLoanApplication | RawMortgageApplication)[] }>(
    await request(`/api/v1/lenders/${lenderId}/applications`, { sessionId: context.sessionId }),
    200,
  );
  if (!body.connected) return { connected: false, institution };
  return { connected: true, institution, data: body.items.map((raw) => normalizeApplication(raw, summaryOf(lender))) };
}

function normalizeApplication(raw: RawLoanApplication | RawMortgageApplication, lender: InstitutionSummary): LoanApplication | MortgageApplication {
  // Live lenders report no balances, so there is no servicing snapshot (not counted as debt).
  const context = { lender, submittedThisSession: false, servicing: null };
  return "mortgage_type" in raw ? normalizeMortgageApplication(raw, context) : normalizeLoanApplication(raw as RawLoanApplication, context);
}

async function schedule(lenderId: LenderId, applicationId: string): Promise<Gated<ScheduleResult>> {
  const context = await institutions();
  const lender = context.items.find((i) => i.id === lenderId)!;
  const institution = metadata(lender);
  if (!context.sessionId || !lender.connected) return { connected: false, institution };
  const body = expect<{ connected: boolean; kind?: ScheduleResult["kind"]; application?: RawLoanApplication | RawMortgageApplication; rows?: RawInstallment[] }>(
    await request(`/api/v1/lenders/${lenderId}/applications/${encodeURIComponent(applicationId)}/schedule`, { sessionId: context.sessionId }),
    200,
  );
  if (!body.connected) return { connected: false, institution };
  if (body.kind === "not_found" || !body.application) return { connected: true, institution, data: { kind: "not_found" } };
  const application = normalizeApplication(body.application, summaryOf(lender));
  return {
    connected: true,
    institution,
    data: body.kind === "schedule" ? { kind: "schedule", application, rows: body.rows ?? [] } : { kind: "declined", application },
  };
}

async function submit<T extends LoanApplication | MortgageApplication>(lenderId: LenderId, payload: Record<string, unknown>): Promise<SubmitResult<T>> {
  const sessionId = await readSessionId();
  if (!sessionId) return { ok: false, status: 401, errors: [{ field: null, message: "Connect this lender before applying." }] };
  const response = await request(`/api/v1/lenders/${lenderId}/applications`, { method: "POST", body: payload, sessionId });
  if (response.status === 201) {
    const lender = (await institutions()).items.find((i) => i.id === lenderId)!;
    return { ok: true, application: normalizeApplication(response.body as RawLoanApplication, summaryOf(lender)) as T };
  }
  if (response.status === 401 || response.status === 422) return { ok: false, status: response.status, errors: detailOf(response.body).errors };
  expect(response, 201);
  throw new Error("unreachable");
}

export const httpProvider: DataProvider = {
  kind: "http",

  async getDashboard() {
    const { accounts, context } = await loadAccounts();
    const transactions = context.sessionId && accounts.length
      ? complete(expect<{ items: RawTransaction[]; errors: [] }>(await request("/api/v1/transactions", { sessionId: context.sessionId }), 200))
      : [];
    const byAccount = new Map(accounts.map((a) => [a.id, a]));
    const [loans, mortgages] = await Promise.all([lenderApplications("loans"), lenderApplications("mortgages")]);
    // "As of" = the newest balance timestamp the banks reported.
    const snapshotDate = accounts.reduce((latest, a) => (a.updatedAt.slice(0, 10) > latest ? a.updatedAt.slice(0, 10) : latest), "0000-00-00");
    return buildDashboard({
      snapshotDate: snapshotDate === "0000-00-00" ? new Date().toISOString().slice(0, 10) : snapshotDate,
      accounts,
      transactions: transactions.filter((t) => byAccount.has(t.account_id)).map((t) => normalizeTransaction(t, byAccount.get(t.account_id)!)),
      loans: loans.connected ? (loans.data as LoanApplication[]) : [],
      mortgages: mortgages.connected ? (mortgages.data as MortgageApplication[]) : [],
      connectedInstitutions: context.items.filter((i) => i.connected).map(summaryOf),
      availableInstitutions: context.items.filter((i) => !i.connected).map(summaryOf),
    });
  },

  async getInsights() {
    const [dashboard, { accounts }] = await Promise.all([httpProvider.getDashboard(), loadAccounts()]);
    return buildSampleInsights(dashboard, accounts);
  },

  async listConnections() {
    return (await institutions()).items.map((i) => ({ institution: metadata(i), connected: i.connected, customer: i.customer }));
  },

  async getConsentStep(institutionId) {
    const known = (await institutions()).items.find((i) => i.id === institutionId);
    // Live codes are only in the service's DEMO_MODE logs, so there is no demoCode here.
    return known ? { step: "email", email: metadata(known).demoEmail } : null;
  },

  async requestCode(institutionId, email) {
    const sessionId = await ensureSessionId();
    const response = await request(`/api/v1/institutions/${encodeURIComponent(institutionId)}/request-code`, { method: "POST", body: { email }, sessionId });
    if (response.status === 202) return { ok: true, message: String((response.body as { message?: string })?.message ?? "Code requested.") };
    if (response.status === 404 || response.status === 422 || response.status === 429) {
      const retry = Number(response.headers.get("Retry-After"));
      return { ok: false, status: response.status, message: detailOf(response.body).message, retryAfterSeconds: Number.isFinite(retry) && retry > 0 ? retry : undefined };
    }
    expect(response, 202);
    throw new Error("unreachable");
  },

  async verifyCode(institutionId, email, code) {
    const sessionId = await ensureSessionId();
    const response = await request(`/api/v1/institutions/${encodeURIComponent(institutionId)}/verify-code`, { method: "POST", body: { email, code }, sessionId });
    if (response.status === 200) {
      const known = (await institutions()).items.find((i) => i.id === institutionId)!;
      return { ok: true, institution: metadata(known) };
    }
    if (response.status === 401 || response.status === 404 || response.status === 422) {
      return { ok: false, status: response.status, message: detailOf(response.body).message };
    }
    expect(response, 200);
    throw new Error("unreachable");
  },

  async disconnect(institutionId) {
    const sessionId = await readSessionId();
    if (sessionId) await request(`/api/v1/institutions/${encodeURIComponent(institutionId)}/connection`, { method: "DELETE", sessionId });
  },

  async resetDemo() {
    // Dropping our reference ends access; the backend expires the idle session.
    (await cookies()).delete(SESSION_COOKIE);
  },

  async listAccounts(filter) {
    return (await loadAccounts(filter?.type)).accounts;
  },

  async getAccount(accountId) {
    const { accounts } = await loadAccounts();
    return accounts.find((account) => account.id === accountId) ?? null;
  },

  async listTransactions(accountId, filters) {
    const account = await httpProvider.getAccount(accountId);
    const sessionId = await readSessionId();
    if (!account || !sessionId) return null;
    const query = new URLSearchParams({ limit: String(filters.limit), offset: String(filters.offset) });
    if (filters.startDate) query.set("start_date", filters.startDate);
    if (filters.endDate) query.set("end_date", filters.endDate);
    if (filters.category) query.set("category", filters.category);
    const response = await request(`/api/v1/accounts/${encodeURIComponent(accountId)}/transactions?${query}`, { sessionId });
    if (response.status === 404) return null;
    const page = expect<RawTransactionPage>(response, 200);
    return { ...page, items: page.items.map((t) => normalizeTransaction(t, account)) };
  },

  async listLoanOffers() {
    return expect<RawLoanOffer[]>(await request("/api/v1/lenders/loans/offers"), 200).map(normalizeLoanOffer);
  },
  async listLoanApplications() {
    return (await lenderApplications("loans")) as Gated<LoanApplication[]>;
  },
  async getLoanSchedule(id) {
    return schedule("loans", id);
  },
  async submitLoanApplication(values) {
    const validated = validateLoanApplication(values, LOAN_TYPES);
    if (!validated.ok) return { ok: false, status: 422, errors: validated.errors };
    return submit<LoanApplication>("loans", { ...validated.value });
  },

  async listMortgageOffers() {
    return expect<RawMortgageOffer[]>(await request("/api/v1/lenders/mortgages/offers"), 200).map(normalizeLoanOffer);
  },
  async listMortgageApplications() {
    return (await lenderApplications("mortgages")) as Gated<MortgageApplication[]>;
  },
  async getMortgageSchedule(id) {
    return schedule("mortgages", id);
  },
  async submitMortgageApplication(values) {
    const validated = validateMortgageApplication(values);
    if (!validated.ok) return { ok: false, status: 422, errors: validated.errors };
    return submit<MortgageApplication>("mortgages", { ...validated.value });
  },
};

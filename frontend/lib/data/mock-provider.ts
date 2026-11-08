import "server-only";
import type {
  Account,
  ConnectableInstitution,
  Connection,
  ConsentStep,
  InstitutionSummary,
  LoanApplication,
  MortgageApplication,
  RawLoanApplication,
  RawMortgageApplication,
  ScheduleResult,
  Transaction,
  TransactionFilters,
} from "@/lib/types";
import { LOAN_TYPES } from "@/lib/types";
import { buildSchedule } from "@/lib/finance/amortization";
import { buildSampleInsights } from "@/lib/finance/insights";
import { buildDashboard, servicingSnapshotFor } from "@/lib/finance/portfolio";
import { decideLoan, decideMortgage, isRuleViolation, validateLoanApplication, validateMortgageApplication } from "@/lib/finance/underwriting";
import { RAW_ACCOUNTS, RAW_TRANSACTIONS } from "./fixtures/bank";
import { DEMO_CONSENT_CODE, INSTITUTIONS, SNAPSHOT_DATE, customerFor, findInstitution } from "./fixtures/institutions";
import {
  RAW_LOAN_OFFERS,
  RAW_MORTGAGE_OFFERS,
  SEEDED_LOAN_APPLICATIONS,
  SEEDED_MORTGAGE_APPLICATIONS,
  SERVICED_FIXTURE_IDS,
  buildRawLoanApplication,
  buildRawMortgageApplication,
} from "./fixtures/lending";
import { normalizeAccount, normalizeLoanApplication, normalizeLoanOffer, normalizeMortgageApplication, normalizeTransaction } from "./normalize";
import type { DataProvider, Gated, RequestCodeResult, SubmitResult, VerifyCodeResult } from "./provider";
import { clearSession, readSession, writeSession, type DemoSession } from "./session";

// Consent rules copied from the services' defaults (config.py).
const CODE_TTL_MS = 5 * 60 * 1000;
const CODE_ATTEMPT_LIMIT = 5;
const REQUEST_COOLDOWN_SECONDS = 30;
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** Optional artificial latency so loading states can be seen in development. */
async function simulateLatency() {
  const ms = Number(process.env.MOCK_LATENCY_MS ?? 0);
  if (Number.isFinite(ms) && ms > 0) await new Promise((resolve) => setTimeout(resolve, Math.min(ms, 5000)));
}

const summaryOf = (institution: ConnectableInstitution): InstitutionSummary => ({
  id: institution.id,
  name: institution.name,
  service: institution.service,
});

const INSTITUTION_SUMMARIES = new Map(INSTITUTIONS.map((institution) => [institution.id, summaryOf(institution)]));

// Fixtures are constant, so normalize them once per server process.
const ALL_ACCOUNTS: readonly Account[] = RAW_ACCOUNTS.map((raw) => normalizeAccount(raw, INSTITUTION_SUMMARIES.get(raw.institution_id)!));
const ALL_TRANSACTIONS: ReadonlyMap<string, readonly Transaction[]> = new Map(
  ALL_ACCOUNTS.map((account) => [account.id, (RAW_TRANSACTIONS.get(account.id) ?? []).map((raw) => normalizeTransaction(raw, account))]),
);

const isConnected = (session: DemoSession, institutionId: string) => session.connections.includes(institutionId);
const byNewest = <T extends { created_at: string; id: string }>(a: T, b: T) =>
  a.created_at === b.created_at ? a.id.localeCompare(b.id) : a.created_at < b.created_at ? 1 : -1;

function connectedAccounts(session: DemoSession): Account[] {
  return ALL_ACCOUNTS.filter((account) => isConnected(session, account.institution.id));
}

function servicingFor(raw: RawLoanApplication | RawMortgageApplication) {
  if (raw.status !== "approved" || !SERVICED_FIXTURE_IDS.has(raw.id)) return null;
  const rows = buildSchedule({ amount: raw.amount, apr: raw.apr, monthlyPayment: raw.monthly_payment, termMonths: raw.term_months, createdAt: raw.created_at });
  return servicingSnapshotFor(rows, SNAPSHOT_DATE, raw.amount);
}

function loanRecords(session: DemoSession): LoanApplication[] {
  const lender = INSTITUTION_SUMMARIES.get("loans")!;
  const sessionIds = new Set(session.loanApplications.map((stored) => stored.id));
  const sessionRaw = session.loanApplications
    .map((stored) => buildRawLoanApplication(stored, { id: stored.id, customerId: "loans-customer-001", createdAt: stored.created_at }))
    .filter((raw): raw is RawLoanApplication => raw !== null);
  return [...SEEDED_LOAN_APPLICATIONS, ...sessionRaw]
    .sort(byNewest)
    .map((raw) => normalizeLoanApplication(raw, { lender, submittedThisSession: sessionIds.has(raw.id), servicing: servicingFor(raw) }));
}

function mortgageRecords(session: DemoSession): MortgageApplication[] {
  const lender = INSTITUTION_SUMMARIES.get("mortgages")!;
  const sessionIds = new Set(session.mortgageApplications.map((stored) => stored.id));
  const sessionRaw = session.mortgageApplications
    .map((stored) => buildRawMortgageApplication(stored, { id: stored.id, customerId: "mortgages-customer-001", createdAt: stored.created_at }))
    .filter((raw): raw is RawMortgageApplication => raw !== null);
  return [...SEEDED_MORTGAGE_APPLICATIONS, ...sessionRaw]
    .sort(byNewest)
    .map((raw) => normalizeMortgageApplication(raw, { lender, submittedThisSession: sessionIds.has(raw.id), servicing: servicingFor(raw) }));
}

function gate<T>(session: DemoSession, institutionId: string, read: () => T): Gated<T> {
  const institution = findInstitution(institutionId)!;
  return isConnected(session, institutionId) ? { connected: true, institution, data: read() } : { connected: false, institution };
}

function scheduleFor(application: LoanApplication | MortgageApplication | undefined): ScheduleResult {
  if (!application) return { kind: "not_found" };
  if (application.status !== "approved") return { kind: "declined", application };
  const rows = buildSchedule({
    amount: application.amount,
    apr: application.apr,
    monthlyPayment: application.monthlyPayment,
    termMonths: application.termMonths,
    createdAt: application.createdAt,
  });
  return { kind: "schedule", application, rows };
}

export const mockProvider: DataProvider = {
  kind: "mock",

  async getDashboard() {
    await simulateLatency();
    const session = await readSession();
    const accounts = connectedAccounts(session);
    return buildDashboard({
      snapshotDate: SNAPSHOT_DATE,
      accounts,
      transactions: accounts.flatMap((account) => ALL_TRANSACTIONS.get(account.id) ?? []),
      loans: isConnected(session, "loans") ? loanRecords(session) : [],
      mortgages: isConnected(session, "mortgages") ? mortgageRecords(session) : [],
      connectedInstitutions: INSTITUTIONS.filter((i) => isConnected(session, i.id)).map(summaryOf),
      availableInstitutions: INSTITUTIONS.filter((i) => !isConnected(session, i.id)).map(summaryOf),
    });
  },

  async getInsights() {
    const [dashboard, accounts] = await Promise.all([mockProvider.getDashboard(), mockProvider.listAccounts()]);
    return buildSampleInsights(dashboard, accounts);
  },

  async listConnections(): Promise<Connection[]> {
    await simulateLatency();
    const session = await readSession();
    return INSTITUTIONS.map((institution) => {
      const connected = isConnected(session, institution.id);
      return { institution, connected, customer: connected ? customerFor(institution.id) : null };
    });
  },

  async getConsentStep(institutionId): Promise<ConsentStep | null> {
    const institution = findInstitution(institutionId);
    if (!institution) return null;
    const session = await readSession();
    const consent = session.consent;
    if (consent && consent.institutionId === institutionId && Date.now() - Date.parse(consent.requestedAt) < CODE_TTL_MS && consent.attempts < CODE_ATTEMPT_LIMIT) {
      return { step: "code", email: consent.email, codeRequestedAt: consent.requestedAt, attemptsRemaining: CODE_ATTEMPT_LIMIT - consent.attempts, demoCode: DEMO_CONSENT_CODE };
    }
    return { step: "email", email: institution.demoEmail, demoCode: DEMO_CONSENT_CODE };
  },

  async requestCode(institutionId, rawEmail): Promise<RequestCodeResult> {
    await simulateLatency();
    if (!findInstitution(institutionId)) return { ok: false, status: 404, message: "Institution not found." };
    const email = rawEmail.trim().toLowerCase();
    if (email.length > 254 || !EMAIL_PATTERN.test(email)) {
      return { ok: false, status: 422, message: "Provide a valid fictional email address." };
    }
    const session = await readSession();
    const prior = session.consent;
    if (prior && prior.institutionId === institutionId && prior.email === email) {
      const elapsed = (Date.now() - Date.parse(prior.requestedAt)) / 1000;
      if (elapsed < REQUEST_COOLDOWN_SECONDS) {
        const retryAfterSeconds = Math.ceil(REQUEST_COOLDOWN_SECONDS - elapsed);
        return { ok: false, status: 429, message: "Please wait before requesting another code.", retryAfterSeconds };
      }
    }
    // Like the service, store a code request even for unregistered emails, so
    // responses never reveal whether an email is registered.
    await writeSession({ ...session, consent: { institutionId, email, requestedAt: new Date().toISOString(), attempts: 0 } });
    return { ok: true, message: "If registered, a mock code was generated." };
  },

  async verifyCode(institutionId, rawEmail, code): Promise<VerifyCodeResult> {
    await simulateLatency();
    const institution = findInstitution(institutionId);
    if (!institution) return { ok: false, status: 404, message: "Institution not found." };
    if (!/^\d{6}$/.test(code)) return { ok: false, status: 422, message: "Enter the six-digit code." };
    const email = rawEmail.trim().toLowerCase();
    const session = await readSession();
    const consent = session.consent;
    const invalid = { ok: false as const, status: 401 as const, message: "Invalid or expired verification code." };
    if (
      !consent ||
      consent.institutionId !== institutionId ||
      consent.email !== email ||
      Date.now() - Date.parse(consent.requestedAt) >= CODE_TTL_MS ||
      consent.attempts >= CODE_ATTEMPT_LIMIT
    ) {
      return invalid;
    }
    if (code !== DEMO_CONSENT_CODE || email !== institution.demoEmail) {
      await writeSession({ ...session, consent: { ...consent, attempts: consent.attempts + 1 } });
      return invalid;
    }
    await writeSession({ ...session, consent: null, connections: [...new Set([...session.connections, institutionId])] });
    return { ok: true, institution };
  },

  async disconnect(institutionId) {
    const session = await readSession();
    await writeSession({
      ...session,
      connections: session.connections.filter((id) => id !== institutionId),
      consent: session.consent?.institutionId === institutionId ? null : session.consent,
    });
  },

  async resetDemo() {
    await clearSession();
  },

  async listAccounts(filter) {
    await simulateLatency();
    const session = await readSession();
    const accounts = connectedAccounts(session);
    return filter?.type ? accounts.filter((account) => account.type === filter.type) : accounts;
  },

  async getAccount(accountId) {
    await simulateLatency();
    const session = await readSession();
    return connectedAccounts(session).find((account) => account.id === accountId) ?? null;
  },

  async listTransactions(accountId, filters: TransactionFilters) {
    await simulateLatency();
    const session = await readSession();
    const account = connectedAccounts(session).find((candidate) => candidate.id === accountId);
    if (!account) return null;
    const limit = Math.min(Math.max(Math.trunc(filters.limit), 1), 100);
    const offset = Math.max(Math.trunc(filters.offset), 0);
    const matching = (ALL_TRANSACTIONS.get(accountId) ?? []).filter(
      (transaction) =>
        (!filters.startDate || transaction.date >= filters.startDate) &&
        (!filters.endDate || transaction.date <= filters.endDate) &&
        (!filters.category || transaction.category === filters.category),
    );
    return { items: matching.slice(offset, offset + limit), total: matching.length, limit, offset };
  },

  async listLoanOffers() {
    return RAW_LOAN_OFFERS.map(normalizeLoanOffer);
  },

  async listLoanApplications() {
    await simulateLatency();
    const session = await readSession();
    return gate(session, "loans", () => loanRecords(session));
  },

  async getLoanSchedule(applicationId) {
    await simulateLatency();
    const session = await readSession();
    return gate(session, "loans", () => scheduleFor(loanRecords(session).find((application) => application.id === applicationId)));
  },

  async submitLoanApplication(values): Promise<SubmitResult<LoanApplication>> {
    await simulateLatency();
    const session = await readSession();
    if (!isConnected(session, "loans")) {
      return { ok: false, status: 401, errors: [{ field: null, message: "Connect Capital Insight Mock Loans before applying." }] };
    }
    const validated = validateLoanApplication(values, LOAN_TYPES);
    if (!validated.ok) return { ok: false, status: 422, errors: validated.errors };
    const offer = RAW_LOAN_OFFERS.find((candidate) => candidate.loan_type === validated.value.loan_type)!;
    const decision = decideLoan(validated.value, offer);
    if (isRuleViolation(decision)) return { ok: false, status: 422, errors: [{ field: null, message: decision.detail }] };
    const stored = { ...validated.value, id: crypto.randomUUID(), created_at: new Date().toISOString() };
    await writeSession({ ...session, loanApplications: [stored, ...session.loanApplications] });
    const application = loanRecords({ ...session, loanApplications: [stored, ...session.loanApplications] }).find((a) => a.id === stored.id)!;
    return { ok: true, application };
  },

  async listMortgageOffers() {
    return RAW_MORTGAGE_OFFERS.map(normalizeLoanOffer);
  },

  async listMortgageApplications() {
    await simulateLatency();
    const session = await readSession();
    return gate(session, "mortgages", () => mortgageRecords(session));
  },

  async getMortgageSchedule(applicationId) {
    await simulateLatency();
    const session = await readSession();
    return gate(session, "mortgages", () => scheduleFor(mortgageRecords(session).find((application) => application.id === applicationId)));
  },

  async submitMortgageApplication(values): Promise<SubmitResult<MortgageApplication>> {
    await simulateLatency();
    const session = await readSession();
    if (!isConnected(session, "mortgages")) {
      return { ok: false, status: 401, errors: [{ field: null, message: "Connect Capital Insight Mock Mortgages before applying." }] };
    }
    const validated = validateMortgageApplication(values);
    if (!validated.ok) return { ok: false, status: 422, errors: validated.errors };
    const decision = decideMortgage(validated.value, RAW_MORTGAGE_OFFERS[0]);
    if (isRuleViolation(decision)) return { ok: false, status: 422, errors: [{ field: null, message: decision.detail }] };
    const stored = { ...validated.value, id: crypto.randomUUID(), created_at: new Date().toISOString() };
    const next = { ...session, mortgageApplications: [stored, ...session.mortgageApplications] };
    await writeSession(next);
    return { ok: true, application: mortgageRecords(next).find((a) => a.id === stored.id)! };
  },
};

/**
 * The one async interface pages and actions use to read and change data.
 *
 * Implementations:
 *  - mock-provider.ts: deterministic fixtures + session-local demo state (default)
 *  - http-provider.ts: placeholder for the future Capital Insight backend
 *
 * Expected outcomes (not connected, declined, validation errors, cooldowns)
 * are return values. Unexpected failures (backend down, bad config) throw and
 * reach the route's error boundary. A provider must never silently fall back
 * to fixtures when a live request fails.
 */
import type {
  Account,
  AccountType,
  ConnectableInstitution,
  Connection,
  ConsentStep,
  Dashboard,
  InsightReport,
  LoanApplication,
  LoanOffer,
  MortgageApplication,
  ScheduleResult,
  TransactionFilters,
  TransactionPage,
} from "@/lib/types";
import type { FieldError } from "@/lib/finance/underwriting";

export type DataSourceKind = "mock" | "http";

/** Records behind a consent the user has not given yet (the services answer 401). */
export type Gated<T> =
  | { connected: false; institution: ConnectableInstitution }
  | { connected: true; institution: ConnectableInstitution; data: T };

export type SubmitResult<T> =
  | { ok: true; application: T }
  | { ok: false; status: 401 | 422; errors: FieldError[] };

export type RequestCodeResult =
  | { ok: true; message: string }
  | { ok: false; status: 404 | 422 | 429; message: string; retryAfterSeconds?: number };

export type VerifyCodeResult = { ok: true; institution: ConnectableInstitution } | { ok: false; status: 401 | 404 | 422; message: string };

export interface DataProvider {
  readonly kind: DataSourceKind;

  getDashboard(): Promise<Dashboard>;
  /** Sample, rule-based output in fixture mode; AI analysis from the backend later. */
  getInsights(): Promise<InsightReport>;

  // Connections (simulated consent)
  listConnections(): Promise<Connection[]>;
  getConsentStep(institutionId: string): Promise<ConsentStep | null>;
  requestCode(institutionId: string, email: string): Promise<RequestCodeResult>;
  verifyCode(institutionId: string, email: string, code: string): Promise<VerifyCodeResult>;
  disconnect(institutionId: string): Promise<void>;
  resetDemo(): Promise<void>;

  // Bank accounts
  listAccounts(filter?: { type?: AccountType }): Promise<Account[]>;
  /** `null` when the account does not exist or is not connected (the service answers 404 for both). */
  getAccount(accountId: string): Promise<Account | null>;
  /** `null` when the account is unavailable. Filters follow the service's inclusive date semantics. */
  listTransactions(accountId: string, filters: TransactionFilters): Promise<TransactionPage | null>;

  // Lending
  listLoanOffers(): Promise<LoanOffer[]>;
  listLoanApplications(): Promise<Gated<LoanApplication[]>>;
  getLoanSchedule(applicationId: string): Promise<Gated<ScheduleResult>>;
  submitLoanApplication(values: Record<string, string>): Promise<SubmitResult<LoanApplication>>;

  listMortgageOffers(): Promise<LoanOffer[]>;
  listMortgageApplications(): Promise<Gated<MortgageApplication[]>>;
  getMortgageSchedule(applicationId: string): Promise<Gated<ScheduleResult>>;
  submitMortgageApplication(values: Record<string, string>): Promise<SubmitResult<MortgageApplication>>;
}

/** Thrown when the configured data source cannot serve requests. */
export class DataSourceUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DataSourceUnavailableError";
  }
}

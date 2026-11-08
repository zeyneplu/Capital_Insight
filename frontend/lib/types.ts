/**
 * Types shared by the data layer and the UI.
 *
 * Two families live here:
 *  1. `Raw*` types mirror the JSON returned by the mock services today
 *     (see services/<name>/app/schemas.py). Money and rates are decimal strings.
 *  2. View models are what pages and components render. They keep the source
 *     service, institution and record ID of every normalized record, so data
 *     from different institutions can never be confused or double counted.
 *
 * The future main backend has no contract yet. Any response shape proposed
 * here for it is marked PROPOSED and must be agreed with the backend developer.
 *
 * This file contains types only (no runtime code), so finance modules can
 * import it under `node --test`.
 */

// ---------------------------------------------------------------------------
// Raw service contracts (current mock services)
// ---------------------------------------------------------------------------

/** Decimal money string, e.g. "16487.05". Never a JS number. */
export type MoneyString = string;
/** Decimal fraction string, e.g. "0.0625" for 6.25%. */
export type RateString = string;
/** Calendar date, YYYY-MM-DD. */
export type IsoDate = string;
/** ISO 8601 date-time. */
export type IsoDateTime = string;

export const ACCOUNT_TYPES = [
  "checking",
  "savings",
  "credit_card",
  "cd",
  "ira",
  "investment",
  "other_asset",
  "other_liability",
  "personal_loan",
  "auto_loan",
  "mortgage",
] as const;
export type AccountType = (typeof ACCOUNT_TYPES)[number];

export const TRANSACTION_CATEGORIES = [
  "groceries",
  "dining",
  "shopping",
  "transportation",
  "utilities",
  "entertainment",
  "rent",
  "healthcare",
  "education",
  "salary",
  "transfers",
  "debt_payment",
  "other",
] as const;
export type TransactionCategory = (typeof TRANSACTION_CATEGORIES)[number];

export const LOAN_TYPES = ["personal_loan", "auto_loan", "mortgage"] as const;
export type LoanType = (typeof LOAN_TYPES)[number];

/** mock_bank `CustomerOut` (identical shape in mock_loan and mock_mortgage). */
export interface RawCustomer {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  date_of_birth: IsoDate;
  synthetic_identity_id: string;
  credit_score: number;
  credit_score_as_of: IsoDate;
  created_at: IsoDateTime;
}

/** mock_bank `InstitutionOut` from GET /v1/institution. */
export interface RawInstitution {
  id: string;
  name: string;
  products: AccountType[];
  synthetic: boolean;
}

/** mock_bank `AccountOut`. Subtype fields are null when they do not apply. */
export interface RawAccount {
  id: string;
  customer_id: string;
  institution_id: string;
  account_type: AccountType;
  account_name: string;
  account_number_last4: string;
  currency: string;
  opening_balance: MoneyString;
  balance: MoneyString;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  apy: RateString | null;
  credit_limit: MoneyString | null;
  purchase_apr: RateString | null;
  minimum_payment: MoneyString | null;
  payment_due_date: IsoDate | null;
  original_principal: MoneyString | null;
  outstanding_principal: MoneyString | null;
  apr: RateString | null;
  monthly_payment: MoneyString | null;
  term_months: number | null;
  maturity_date: IsoDate | null;
  account_value: MoneyString | null;
  account_subtype: string | null;
}

/** mock_bank `TransactionOut`. `amount` is nonnegative; `direction` gives its effect. */
export interface RawTransaction {
  id: string;
  account_id: string;
  transaction_date: IsoDate;
  description: string;
  merchant: string;
  category: TransactionCategory;
  amount: MoneyString;
  direction: "credit" | "debit";
  transaction_type: string;
  created_at: IsoDateTime;
}

/** mock_bank `TransactionPage`, newest first. */
export interface RawTransactionPage {
  items: RawTransaction[];
  total: number;
  limit: number;
  offset: number;
}

/** mock_loan `LenderOut` / mock_mortgage `LenderOut` (product list key differs). */
export interface RawLender {
  id: string;
  name: string;
  loan_types?: LoanType[];
  mortgage_types?: "mortgage"[];
  synthetic: boolean;
}

/** mock_loan `Offer`. */
export interface RawLoanOffer {
  loan_type: LoanType;
  name: string;
  minimum_amount: MoneyString;
  maximum_amount: MoneyString;
  apr: RateString;
  terms_months: number[];
  currency: string;
  simulated: boolean;
}

/** mock_mortgage `Offer`. */
export interface RawMortgageOffer extends Omit<RawLoanOffer, "loan_type"> {
  mortgage_type: "mortgage";
}

/** mock_loan `ApplicationOut` (GET /v1/loans returns only approved ones). */
export interface RawLoanApplication {
  id: string;
  customer_id: string;
  loan_type: LoanType;
  amount: MoneyString;
  term_months: number;
  annual_income: MoneyString;
  existing_monthly_debt: MoneyString;
  credit_score: number;
  apr: RateString;
  monthly_payment: MoneyString;
  status: "approved" | "declined";
  decision_reason: string;
  created_at: IsoDateTime;
  simulated: boolean;
}

/** mock_mortgage `ApplicationOut`. `amount` is calculated by the service. */
export interface RawMortgageApplication {
  id: string;
  customer_id: string;
  mortgage_type: "mortgage";
  property_value: MoneyString;
  down_payment: MoneyString;
  amount: MoneyString;
  loan_to_value: RateString;
  term_months: number;
  annual_income: MoneyString;
  existing_monthly_debt: MoneyString;
  credit_score: number;
  apr: RateString;
  monthly_payment: MoneyString;
  status: "approved" | "declined";
  decision_reason: string;
  created_at: IsoDateTime;
  simulated: boolean;
}

/** Shared `Installment` row from /schedule endpoints. */
export interface RawInstallment {
  installment: number;
  due_date: IsoDate;
  payment: MoneyString;
  principal: MoneyString;
  interest: MoneyString;
  remaining_balance: MoneyString;
}

// ---------------------------------------------------------------------------
// View models
// ---------------------------------------------------------------------------

export type ServiceKind = "mock_bank" | "mock_loan" | "mock_mortgage" | "plaid";

/** Where a normalized record came from. Never drop this when aggregating. */
export interface SourceRef {
  service: ServiceKind;
  institutionId: string;
  recordId: string;
}

export interface InstitutionSummary {
  id: string;
  name: string;
  service: ServiceKind;
}

/** Assets add to net worth; liabilities are amounts owed. */
export type BalanceClass = "asset" | "liability";

export interface CreditScoreSummary {
  score: number | null;
  minimum: number;
  maximum: number;
  model: string;
  synthetic: boolean;
  as_of: IsoDate | null;
  sources: string[];
  status: "available" | "connect_bank" | "unavailable" | "conflicting_profiles";
}

export interface Account {
  id: string;
  source: SourceRef;
  institution: InstitutionSummary;
  type: AccountType;
  classification: BalanceClass;
  name: string;
  last4: string;
  currency: string;
  /** For liabilities this is the amount owed (positive). */
  balance: MoneyString;
  openingBalance: MoneyString | null;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
  details: {
    apy: RateString | null;
    creditLimit: MoneyString | null;
    purchaseApr: RateString | null;
    minimumPayment: MoneyString | null;
    paymentDueDate: IsoDate | null;
    originalPrincipal: MoneyString | null;
    outstandingPrincipal: MoneyString | null;
    apr: RateString | null;
    monthlyPayment: MoneyString | null;
    termMonths: number | null;
    maturityDate: IsoDate | null;
    accountValue: MoneyString | null;
    subtype: string | null;
  };
}

export interface Transaction {
  id: string;
  source: SourceRef;
  accountId: string;
  date: IsoDate;
  description: string;
  merchant: string;
  category: TransactionCategory;
  amount: MoneyString;
  direction: "credit" | "debit";
  type: string;
  /** How this entry changed the account balance as reported (owed amount for liabilities). */
  balanceEffect: "increase" | "decrease";
}

export interface TransactionFilters {
  limit: number;
  offset: number;
  startDate?: IsoDate;
  endDate?: IsoDate;
  category?: TransactionCategory;
}

export interface TransactionPage {
  items: Transaction[];
  total: number;
  limit: number;
  offset: number;
}

export type TransactionOperation = "deposit" | "withdrawal" | "salary" | "purchase" | "payment" | "refund" | "transfer" | "card_payment" | "loan_payment" | "interest" | "fee";
export interface TransactionInput {
  request_id: string;
  operation: TransactionOperation;
  amount: string;
  counterparty_account_id?: string;
  category?: string;
  merchant?: string;
  description?: string;
}

export interface LoanOffer {
  loanType: LoanType;
  name: string;
  minimumAmount: MoneyString;
  maximumAmount: MoneyString;
  apr: RateString;
  termsMonths: number[];
  currency: string;
  simulated: boolean;
}

/**
 * A fixture-only servicing snapshot. The mock lenders expose the original
 * financed amount and a projected schedule, never a live balance or payment
 * history, so the dashboard needs this explicit, labeled assumption.
 */
export interface ServicingSnapshot {
  basis: "fixture";
  asOf: IsoDate;
  /** Assumes every projected installment due on or before `asOf` was paid. */
  installmentsAssumedPaid: number;
  estimatedOutstanding: MoneyString;
  nextDueDate: IsoDate | null;
  nextPayment: MoneyString | null;
  note: string;
}

interface ApplicationBase {
  id: string;
  source: SourceRef;
  lender: InstitutionSummary;
  /** Original financed amount, not a current balance. */
  amount: MoneyString;
  termMonths: number;
  apr: RateString;
  monthlyPayment: MoneyString;
  status: "approved" | "declined";
  decisionReason: string;
  createdAt: IsoDateTime;
  applicant: {
    annualIncome: MoneyString;
    existingMonthlyDebt: MoneyString;
    creditScore: number;
  };
  /** True when the application was submitted in this browser session (fixture mode). */
  submittedThisSession: boolean;
  servicing: ServicingSnapshot | null;
}

export interface LoanApplication extends ApplicationBase {
  kind: "loan";
  loanType: LoanType;
}

export interface MortgageApplication extends ApplicationBase {
  kind: "mortgage";
  propertyValue: MoneyString;
  downPayment: MoneyString;
  loanToValue: RateString;
}

export type Installment = RawInstallment;

/** Result of reading a schedule: declined applications have none (service 409). */
export type ScheduleResult =
  | { kind: "schedule"; application: LoanApplication | MortgageApplication; rows: Installment[] }
  | { kind: "declined"; application: LoanApplication | MortgageApplication }
  | { kind: "not_found" };

// ---------------------------------------------------------------------------
// Connections (simulated consent)
// ---------------------------------------------------------------------------

export interface ConnectableInstitution extends InstitutionSummary {
  shortName: string;
  description: string;
  /** Products as advertised by the service (account types or loan types). */
  products: string[];
  demoEmail: string;
  defaultPort: number;
}

export interface Connection {
  institution: ConnectableInstitution;
  connected: boolean;
  customer: RawCustomer | null;
}

export type ConsentStep = (
  | { step: "email"; email: string }
  | { step: "code"; email: string; codeRequestedAt: IsoDateTime; attemptsRemaining: number }
) & {
  /** Fixture mode only: the documented demo code. Live services never expose a code. */
  demoCode?: string;
};

// ---------------------------------------------------------------------------
// Dashboard (PROPOSED aggregate shape for the future main backend)
// ---------------------------------------------------------------------------

export interface BreakdownItem {
  id: string;
  label: string;
  institutionName: string;
  type: AccountType | LoanType;
  amount: MoneyString;
  source: SourceRef;
  /** e.g. "Fixture servicing snapshot" for lender records. */
  basisNote?: string;
}

export interface CategoryTotal {
  category: TransactionCategory;
  amount: MoneyString;
  count: number;
}

export interface MonthlyCashFlow {
  /** YYYY-MM */
  month: string;
  income: MoneyString;
  spending: MoneyString;
  /** True when the fixture window does not cover the whole month. */
  partial: boolean;
}

export interface Obligation {
  id: string;
  label: string;
  institutionName: string;
  amount: MoneyString;
  amountLabel: string;
  dueDate: IsoDate | null;
  source: SourceRef;
  note?: string;
}

export interface Dashboard {
  snapshotDate: IsoDate;
  totals: { assets: MoneyString; liabilities: MoneyString; netWorth: MoneyString };
  assets: BreakdownItem[];
  liabilities: BreakdownItem[];
  spending: {
    windowStart: IsoDate;
    windowEnd: IsoDate;
    total: MoneyString;
    byCategory: CategoryTotal[];
    excludedCategories: TransactionCategory[];
  };
  cashFlow: MonthlyCashFlow[];
  obligations: Obligation[];
  connectedInstitutions: InstitutionSummary[];
  /** Institutions available but not connected in this session. */
  availableInstitutions: InstitutionSummary[];
}

// ---------------------------------------------------------------------------
// Insights (PROPOSED: the backend will supply Nemotron-generated analysis)
// ---------------------------------------------------------------------------

export interface Insight {
  id: string;
  title: string;
  body: string;
  tone: "good" | "warn" | "info";
  metric?: { label: string; value: string };
  /** The figures the insight was computed from, shown for transparency. */
  basis: string[];
}

export interface InsightReport {
  /** "sample-rules" until the backend provides real AI analysis. */
  source: "sample-rules" | "backend-ai";
  snapshotDate: IsoDate;
  items: Insight[];
}

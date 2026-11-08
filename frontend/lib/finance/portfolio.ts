/**
 * Pure aggregation from normalized records to the dashboard view model.
 *
 * Every total is derived from the same records the account pages show, so the
 * dashboard can never disagree with the detail views. All sums use integer
 * cents. When the main backend exists it may return this shape directly
 * (PROPOSED contract; see `Dashboard` in lib/types.ts).
 */
import type {
  Account,
  BreakdownItem,
  CategoryTotal,
  Dashboard,
  InstitutionSummary,
  Installment,
  IsoDate,
  LoanApplication,
  MonthlyCashFlow,
  MortgageApplication,
  Obligation,
  ServicingSnapshot,
  Transaction,
  TransactionCategory,
} from "../types.ts";
import { fromCents, toCents } from "./money.ts";

/** Categories that move money between the user's own accounts or are income. */
export const NON_SPENDING_CATEGORIES: readonly TransactionCategory[] = ["salary", "transfers", "debt_payment"];

const LOAN_LABELS = { personal_loan: "Personal loan", auto_loan: "Auto loan", mortgage: "Mortgage loan" } as const;

/** Account types whose debits count as spending. Loan accounts only receive payments. */
const SPENDING_ACCOUNT_TYPES = new Set(["checking", "savings", "credit_card"]);

export function addDays(isoDate: IsoDate, days: number): IsoDate {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function isSpending(transaction: Transaction, account: Pick<Account, "type">): boolean {
  return (
    transaction.direction === "debit" &&
    SPENDING_ACCOUNT_TYPES.has(account.type) &&
    !NON_SPENDING_CATEGORIES.includes(transaction.category)
  );
}

/**
 * Builds the fixture-only servicing snapshot for an approved lender record:
 * it ASSUMES every projected installment due on or before `asOf` was paid.
 */
export function servicingSnapshotFor(schedule: readonly Installment[], asOf: IsoDate, originalAmount: string): ServicingSnapshot {
  const paid = schedule.filter((row) => row.due_date <= asOf);
  const next = schedule.find((row) => row.due_date > asOf) ?? null;
  return {
    basis: "fixture",
    asOf,
    installmentsAssumedPaid: paid.length,
    estimatedOutstanding: paid.at(-1)?.remaining_balance ?? originalAmount,
    nextDueDate: next?.due_date ?? null,
    nextPayment: next?.payment ?? null,
    note: "Demo servicing snapshot. The lender API reports the original amount and a projected schedule only; this assumes scheduled payments were made.",
  };
}

function sumBy<T>(items: readonly T[], amount: (item: T) => string): string {
  let total = 0n;
  for (const item of items) total += toCents(amount(item));
  return fromCents(total);
}

function monthsBetween(start: IsoDate, end: IsoDate): string[] {
  const months: string[] = [];
  let [year, month] = start.split("-").map(Number);
  const [endYear, endMonth] = end.split("-").map(Number);
  while (year < endYear || (year === endYear && month <= endMonth)) {
    months.push(`${year}-${String(month).padStart(2, "0")}`);
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  return months;
}

function lastDayOfMonth(yearMonth: string): IsoDate {
  const [year, month] = yearMonth.split("-").map(Number);
  return new Date(Date.UTC(year, month, 0)).toISOString().slice(0, 10);
}

export interface PortfolioInput {
  snapshotDate: IsoDate;
  accounts: readonly Account[];
  /** Transactions for exactly the accounts above. */
  transactions: readonly Transaction[];
  loans: readonly LoanApplication[];
  mortgages: readonly MortgageApplication[];
  connectedInstitutions: InstitutionSummary[];
  availableInstitutions: InstitutionSummary[];
  /** Spending window length in days, ending on the snapshot date (inclusive). */
  spendingWindowDays?: number;
  /** Obligations due within this many days after the snapshot are listed. */
  obligationHorizonDays?: number;
}

export function buildDashboard(input: PortfolioInput): Dashboard {
  const windowDays = input.spendingWindowDays ?? 30;
  const horizonDays = input.obligationHorizonDays ?? 45;
  const accountsById = new Map(input.accounts.map((account) => [account.id, account]));

  // --- Assets and liabilities -------------------------------------------------
  const assets: BreakdownItem[] = input.accounts
    .filter((account) => account.classification === "asset")
    .map((account) => ({
      id: account.id,
      label: account.name,
      institutionName: account.institution.name,
      type: account.type,
      amount: account.balance,
      source: account.source,
    }));

  const liabilities: BreakdownItem[] = input.accounts
    .filter((account) => account.classification === "liability")
    .map((account) => ({
      id: account.id,
      label: account.name,
      institutionName: account.institution.name,
      type: account.type,
      amount: account.balance,
      source: account.source,
    }));

  // Lender records count only when an explicit servicing snapshot exists.
  // Applications approved in this demo session are not funded, so they are not debt.
  for (const application of [...input.loans, ...input.mortgages]) {
    if (application.status !== "approved" || !application.servicing) continue;
    liabilities.push({
      id: application.id,
      label: application.kind === "mortgage" ? "Mortgage" : LOAN_LABELS[application.loanType],
      institutionName: application.lender.name,
      type: application.kind === "mortgage" ? "mortgage" : application.loanType,
      amount: application.servicing.estimatedOutstanding,
      source: application.source,
      basisNote: "Fixture servicing snapshot",
    });
  }

  const totalAssets = toCents(sumBy(assets, (item) => item.amount));
  const totalLiabilities = toCents(sumBy(liabilities, (item) => item.amount));

  // --- Spending -----------------------------------------------------------------
  const windowStart = addDays(input.snapshotDate, -(windowDays - 1));
  const spendingTransactions = input.transactions.filter((transaction) => {
    const account = accountsById.get(transaction.accountId);
    return account !== undefined && isSpending(transaction, account);
  });
  const inWindow = spendingTransactions.filter(
    (transaction) => transaction.date >= windowStart && transaction.date <= input.snapshotDate,
  );
  const byCategoryMap = new Map<TransactionCategory, { cents: bigint; count: number }>();
  for (const transaction of inWindow) {
    const entry = byCategoryMap.get(transaction.category) ?? { cents: 0n, count: 0 };
    entry.cents += toCents(transaction.amount);
    entry.count += 1;
    byCategoryMap.set(transaction.category, entry);
  }
  const byCategory: CategoryTotal[] = [...byCategoryMap.entries()]
    .map(([category, { cents, count }]) => ({ category, amount: fromCents(cents), count }))
    .sort((a, b) => {
      const difference = toCents(b.amount) - toCents(a.amount);
      return difference === 0n ? a.category.localeCompare(b.category) : difference > 0n ? 1 : -1;
    });

  // --- Monthly cash flow ------------------------------------------------------------
  const dataStart = input.transactions.reduce<IsoDate | null>(
    (earliest, transaction) => (earliest === null || transaction.date < earliest ? transaction.date : earliest),
    null,
  );
  // Months with less than a week of data would read as a misleading "month".
  const minimumCoverageDays = 7;
  const coveredDays = (month: string) => {
    const first = `${month}-01` < (dataStart ?? "") ? dataStart! : `${month}-01`;
    const last = lastDayOfMonth(month) > input.snapshotDate ? input.snapshotDate : lastDayOfMonth(month);
    return (Date.parse(`${last}T00:00:00Z`) - Date.parse(`${first}T00:00:00Z`)) / 86_400_000 + 1;
  };
  const cashFlow: MonthlyCashFlow[] = dataStart
    ? monthsBetween(dataStart, input.snapshotDate).filter((month) => coveredDays(month) >= minimumCoverageDays).map((month) => {
        const inMonth = (transaction: Transaction) => transaction.date.startsWith(month) && transaction.date <= input.snapshotDate;
        const income = input.transactions.filter(
          (transaction) => inMonth(transaction) && transaction.direction === "credit" && transaction.category === "salary",
        );
        const spending = spendingTransactions.filter(inMonth);
        return {
          month,
          income: sumBy(income, (t) => t.amount),
          spending: sumBy(spending, (t) => t.amount),
          partial: `${month}-01` < dataStart || lastDayOfMonth(month) > input.snapshotDate,
        };
      })
    : [];

  // --- Upcoming obligations -----------------------------------------------------------
  const horizon = addDays(input.snapshotDate, horizonDays);
  const obligations: Obligation[] = [];
  for (const account of input.accounts) {
    if (account.type === "credit_card" && account.details.minimumPayment && toCents(account.balance) > 0n) {
      obligations.push({
        id: `${account.id}-minimum`,
        label: `${account.name} minimum payment`,
        institutionName: account.institution.name,
        amount: account.details.minimumPayment,
        amountLabel: "Minimum due",
        dueDate: account.details.paymentDueDate,
        source: account.source,
        note: `Statement balance ${account.balance}`,
      });
    } else if (account.classification === "liability" && account.details.monthlyPayment) {
      obligations.push({
        id: `${account.id}-monthly`,
        label: `${account.name} payment`,
        institutionName: account.institution.name,
        amount: account.details.monthlyPayment,
        amountLabel: "Monthly payment",
        dueDate: account.details.paymentDueDate,
        source: account.source,
        note: account.details.paymentDueDate ? undefined : "Due date not provided by the institution",
      });
    }
  }
  for (const application of [...input.loans, ...input.mortgages]) {
    const servicing = application.servicing;
    if (application.status !== "approved" || !servicing?.nextDueDate || !servicing.nextPayment) continue;
    obligations.push({
      id: `${application.id}-next`,
      label: application.kind === "mortgage" ? "Mortgage installment" : "Loan installment",
      institutionName: application.lender.name,
      amount: servicing.nextPayment,
      amountLabel: "Scheduled principal + interest",
      dueDate: servicing.nextDueDate,
      source: application.source,
      note: "From the projected schedule",
    });
  }
  const upcoming = obligations
    .filter((obligation) => obligation.dueDate === null || (obligation.dueDate > input.snapshotDate && obligation.dueDate <= horizon))
    .sort((a, b) => {
      if (a.dueDate === b.dueDate) return a.label.localeCompare(b.label);
      if (a.dueDate === null) return 1;
      if (b.dueDate === null) return -1;
      return a.dueDate < b.dueDate ? -1 : 1;
    });

  return {
    snapshotDate: input.snapshotDate,
    totals: {
      assets: fromCents(totalAssets),
      liabilities: fromCents(totalLiabilities),
      netWorth: fromCents(totalAssets - totalLiabilities),
    },
    assets,
    liabilities,
    spending: {
      windowStart,
      windowEnd: input.snapshotDate,
      total: sumBy(inWindow, (t) => t.amount),
      byCategory,
      excludedCategories: [...NON_SPENDING_CATEGORIES],
    },
    cashFlow,
    obligations: upcoming,
    connectedInstitutions: input.connectedInstitutions,
    availableInstitutions: input.availableInstitutions,
  };
}

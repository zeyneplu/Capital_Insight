/**
 * Display formatting. Money and rates arrive as decimal strings and are passed
 * to Intl.NumberFormat as strings, which formats them exactly (no float
 * conversion). Dates are date-only strings formatted in UTC so a reader in
 * any time zone sees the same calendar day the service sent.
 */
import type { AccountType, LoanType, TransactionCategory } from "./types";

type Numeric = `${number}`;

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const currencySigned = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", signDisplay: "exceptZero" });
const currencyWhole = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const percent2 = new Intl.NumberFormat("en-US", { style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const percent0 = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 0 });
const integer = new Intl.NumberFormat("en-US");

const dateFormat = new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
const shortDateFormat = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const monthFormat = new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", timeZone: "UTC" });
const dateTimeFormat = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  timeZone: "UTC",
  timeZoneName: "short",
});

/** "16487.05" -> "$16,487.05" */
export function formatMoney(value: string, options: { signed?: boolean; whole?: boolean } = {}): string {
  const formatter = options.signed ? currencySigned : options.whole ? currencyWhole : currency;
  return formatter.format(value as Numeric);
}

/** "0.0625" -> "6.25%" (APR/APY), or whole percent for ratios like LTV. */
export function formatRate(value: string, options: { whole?: boolean } = {}): string {
  return (options.whole ? percent0 : percent2).format(value as Numeric);
}

/** For display-only ratios that were already computed as numbers (e.g. utilization). */
export function formatRatio(value: number, options: { whole?: boolean } = {}): string {
  return (options.whole ? percent0 : percent2).format(value);
}

export function formatInteger(value: number): string {
  return integer.format(value);
}

const asUtcDate = (isoDate: string) => new Date(`${isoDate.slice(0, 10)}T00:00:00Z`);

/** "2026-11-21" -> "Nov 21, 2026" */
export function formatDate(isoDate: string): string {
  return dateFormat.format(asUtcDate(isoDate));
}

/** "2026-11-21" -> "Nov 21" */
export function formatShortDate(isoDate: string): string {
  return shortDateFormat.format(asUtcDate(isoDate));
}

/** "2026-09" -> "Sep 2026" */
export function formatMonth(yearMonth: string): string {
  return monthFormat.format(new Date(`${yearMonth}-01T00:00:00Z`));
}

export function formatDateTime(isoTimestamp: string): string {
  return dateTimeFormat.format(new Date(isoTimestamp));
}

/** 360 -> "30 years", 36 -> "3 years", 30 -> "30 months" */
export function formatTerm(months: number): string {
  if (months % 12 === 0) {
    const years = months / 12;
    return `${years} ${years === 1 ? "year" : "years"}`;
  }
  return `${months} months`;
}

export const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  checking: "Checking",
  savings: "Savings",
  credit_card: "Credit card",
  cd: "CD",
  ira: "IRA",
  personal_loan: "Personal loan",
  auto_loan: "Auto loan",
  mortgage: "Mortgage",
};

export const LOAN_TYPE_LABELS: Record<LoanType, string> = {
  personal_loan: "Personal loan",
  auto_loan: "Auto loan",
  mortgage: "Mortgage",
};

export const CATEGORY_LABELS: Record<TransactionCategory, string> = {
  groceries: "Groceries",
  dining: "Dining",
  shopping: "Shopping",
  transportation: "Transportation",
  utilities: "Utilities",
  entertainment: "Entertainment",
  rent: "Rent",
  healthcare: "Healthcare",
  education: "Education",
  salary: "Salary",
  transfers: "Transfers",
  debt_payment: "Debt payment",
  other: "Other",
};

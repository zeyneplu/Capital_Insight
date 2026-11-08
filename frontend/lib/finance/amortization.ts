/**
 * Repayment math that mirrors `payment_for` and `schedule_for` in
 * services/mock_loan/app/loan_service.py and
 * services/mock_mortgage/app/mortgage_service.py.
 *
 * The services use Python Decimal with 40 significant digits. We reproduce that
 * with 40-digit fixed-point bigint arithmetic, so the frontend preview and the
 * fixture provider produce the same cents the live services would. Golden
 * values generated from the real Python code live in ./golden/.
 */
import { applyRate, divRoundHalfUp, fromCents, minCents, parseDecimal, pow10, toCents, type Cents } from "./money.ts";

/** Fixed-point scale: 10^40 matches the services' `context.prec = 40`. */
const FIXED = pow10(40);

function fixedMul(a: bigint, b: bigint): bigint {
  return (a * b) / FIXED;
}

function fixedPow(base: bigint, exponent: number): bigint {
  let result = FIXED;
  let factor = base;
  let remaining = exponent;
  while (remaining > 0) {
    if (remaining & 1) result = fixedMul(result, factor);
    factor = fixedMul(factor, factor);
    remaining >>= 1;
  }
  return result;
}

/**
 * Level monthly payment for a fully amortizing loan:
 * amount * r / (1 - (1 + r)^-n), with r = apr / 12, rounded half up to the cent.
 */
export function monthlyPaymentCents(amount: Cents, apr: string, termMonths: number): Cents {
  if (!Number.isInteger(termMonths) || termMonths < 1) {
    throw new RangeError("termMonths must be a positive integer");
  }
  const rate = parseDecimal(apr);
  if (rate.units === 0n) return divRoundHalfUp(amount, BigInt(termMonths));
  const monthlyRate = (rate.units * FIXED) / (pow10(rate.scale) * 12n);
  const growth = fixedPow(FIXED + monthlyRate, termMonths);
  const discount = (FIXED * FIXED) / growth; // (1 + r)^-n in fixed point
  return divRoundHalfUp(amount * monthlyRate, FIXED - discount);
}

/** String-in, string-out convenience wrapper used by forms and providers. */
export function monthlyPayment(amount: string, apr: string, termMonths: number): string {
  return fromCents(monthlyPaymentCents(toCents(amount), apr, termMonths));
}

/** One row of a projected schedule, in the services' `Installment` shape. */
export interface ScheduleRow {
  installment: number;
  due_date: string;
  payment: string;
  principal: string;
  interest: string;
  remaining_balance: string;
}

export interface ScheduleInput {
  amount: string;
  apr: string;
  monthlyPayment: string;
  termMonths: number;
  /** The application's `created_at` (ISO date-time). Due dates count from its UTC date. */
  createdAt: string;
}

/** Calendar date (YYYY-MM-DD) of an ISO timestamp in UTC, like Python's `.date()` on a UTC datetime. */
export function utcDateOf(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) throw new RangeError(`Invalid timestamp: ${isoTimestamp}`);
  return date.toISOString().slice(0, 10);
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/**
 * Adds whole months to a YYYY-MM-DD date, clamping the day to the target
 * month's length (Jan 31 + 1 month = Feb 28/29), exactly like the services.
 */
export function addMonthsClamped(isoDate: string, months: number): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const index = year * 12 + (month - 1) + months;
  const targetYear = Math.floor(index / 12);
  const targetMonth = (index % 12) + 1;
  const targetDay = Math.min(day, daysInMonth(targetYear, targetMonth));
  return `${String(targetYear).padStart(4, "0")}-${String(targetMonth).padStart(2, "0")}-${String(targetDay).padStart(2, "0")}`;
}

/**
 * Projected repayment schedule. This is a preview of scheduled principal and
 * interest, not a record of payments actually made.
 */
export function buildSchedule(input: ScheduleInput): ScheduleRow[] {
  const origin = utcDateOf(input.createdAt);
  const scheduled = toCents(input.monthlyPayment);
  let balance = toCents(input.amount);
  const rows: ScheduleRow[] = [];
  for (let number = 1; number <= input.termMonths; number += 1) {
    const interest = applyRate(balance, input.apr, 12n);
    // The final installment clears any rounding residue, as the services do.
    const payment = number === input.termMonths ? balance + interest : minCents(scheduled, balance + interest);
    const principal = payment - interest;
    balance -= principal;
    rows.push({
      installment: number,
      due_date: addMonthsClamped(origin, number),
      payment: fromCents(payment),
      principal: fromCents(principal),
      interest: fromCents(interest),
      remaining_balance: fromCents(balance),
    });
  }
  return rows;
}

export interface ScheduleTotals {
  totalPayments: string;
  totalInterest: string;
  totalPrincipal: string;
  finalDueDate: string | null;
}

export function summarizeSchedule(rows: readonly ScheduleRow[]): ScheduleTotals {
  let payments = 0n;
  let interest = 0n;
  let principal = 0n;
  for (const row of rows) {
    payments += toCents(row.payment);
    interest += toCents(row.interest);
    principal += toCents(row.principal);
  }
  return {
    totalPayments: fromCents(payments),
    totalInterest: fromCents(interest),
    totalPrincipal: fromCents(principal),
    finalDueDate: rows.at(-1)?.due_date ?? null,
  };
}

export interface YearlyScheduleBucket {
  /** 1-based loan year (installments 1-12 are year 1). */
  loanYear: number;
  principal: string;
  interest: string;
  endingBalance: string;
}

/** Groups installments into 12-month loan years, for charts and summaries. */
export function groupScheduleByLoanYear(rows: readonly ScheduleRow[]): YearlyScheduleBucket[] {
  const buckets: YearlyScheduleBucket[] = [];
  for (let start = 0; start < rows.length; start += 12) {
    const slice = rows.slice(start, start + 12);
    let principal = 0n;
    let interest = 0n;
    for (const row of slice) {
      principal += toCents(row.principal);
      interest += toCents(row.interest);
    }
    buckets.push({
      loanYear: start / 12 + 1,
      principal: fromCents(principal),
      interest: fromCents(interest),
      endingBalance: slice.at(-1)!.remaining_balance,
    });
  }
  return buckets;
}

/**
 * Fictional application rules mirrored from `build_application` in the mock
 * loan and mortgage services. These are demo rules, not real underwriting or
 * a lending recommendation.
 *
 * Validation errors use the same shape as FastAPI's 422 response so the UI
 * can render live-service errors and fixture errors with one component.
 */
import { monthlyPaymentCents } from "./amortization.ts";
import { divRoundHalfEven, formatScaled, fromCents, isMoneyString, toCents, type Cents } from "./money.ts";

export interface FieldError {
  /** Request field name, e.g. "amount". `null` for whole-request errors. */
  field: string | null;
  message: string;
}

export type Validated<T> = { ok: true; value: T } | { ok: false; errors: FieldError[] };

export interface LoanApplicationInput {
  loan_type: string;
  amount: string;
  term_months: number;
  annual_income: string;
  existing_monthly_debt: string;
  credit_score: number;
}

export interface MortgageApplicationInput {
  mortgage_type: "mortgage";
  property_value: string;
  down_payment: string;
  term_months: number;
  annual_income: string;
  existing_monthly_debt: string;
  credit_score: number;
}

/** The subset of a public offer that the rules depend on. */
export interface ProductRules {
  minimum_amount: string;
  maximum_amount: string;
  apr: string;
  terms_months: number[];
}

export interface Decision {
  status: "approved" | "declined";
  decision_reason: string;
  apr: string;
  monthly_payment: string;
}

export interface MortgageDecision extends Decision {
  amount: string;
  loan_to_value: string;
}

/** A business-rule rejection: the service answers 422 with a single detail string. */
export interface RuleViolation {
  status: 422;
  detail: string;
}

type FormValues = Record<string, string | undefined>;

const MAX_DIGITS = 14;

function readMoney(
  values: FormValues,
  field: string,
  label: string,
  bounds: { min: Cents; minInclusive: boolean; max: Cents },
  errors: FieldError[],
): string {
  const raw = (values[field] ?? "").trim().replace(/,/g, "");
  if (raw === "") {
    errors.push({ field, message: `${label} is required.` });
    return "0.00";
  }
  if (!isMoneyString(raw) || raw.startsWith("-")) {
    errors.push({ field, message: `${label} must be a dollar amount with at most two decimal places.` });
    return "0.00";
  }
  const cents = toCents(raw);
  if (cents.toString().length > MAX_DIGITS) {
    errors.push({ field, message: `${label} has too many digits.` });
  } else if (bounds.minInclusive ? cents < bounds.min : cents <= bounds.min) {
    errors.push({
      field,
      message: bounds.minInclusive
        ? `${label} must be at least $${fromCents(bounds.min)}.`
        : `${label} must be greater than $${fromCents(bounds.min)}.`,
    });
  } else if (cents > bounds.max) {
    errors.push({ field, message: `${label} must be at most $${fromCents(bounds.max)}.` });
  }
  return fromCents(cents);
}

function readInteger(values: FormValues, field: string, label: string, min: number, max: number, errors: FieldError[]): number {
  const raw = (values[field] ?? "").trim();
  if (!/^\d+$/.test(raw)) {
    errors.push({ field, message: `${label} must be a whole number.` });
    return 0;
  }
  const value = Number(raw);
  if (value < min || value > max) errors.push({ field, message: `${label} must be between ${min} and ${max}.` });
  return value;
}

const DOLLARS = (value: number) => BigInt(value) * 100n;

/** Field-level checks equivalent to the loan service's `ApplicationIn` schema. */
export function validateLoanApplication(values: FormValues, loanTypes: readonly string[]): Validated<LoanApplicationInput> {
  const errors: FieldError[] = [];
  const loan_type = (values.loan_type ?? "").trim();
  if (!loanTypes.includes(loan_type)) errors.push({ field: "loan_type", message: "Choose a loan product." });
  const value: LoanApplicationInput = {
    loan_type,
    amount: readMoney(values, "amount", "Amount", { min: 0n, minInclusive: false, max: DOLLARS(750_000) }, errors),
    term_months: readInteger(values, "term_months", "Term", 1, 360, errors),
    annual_income: readMoney(values, "annual_income", "Annual income", { min: 0n, minInclusive: false, max: DOLLARS(100_000_000) }, errors),
    existing_monthly_debt: readMoney(values, "existing_monthly_debt", "Existing monthly debt", { min: 0n, minInclusive: true, max: DOLLARS(10_000_000) }, errors),
    credit_score: readInteger(values, "credit_score", "Credit score", 300, 850, errors),
  };
  return errors.length ? { ok: false, errors } : { ok: true, value };
}

/** Field-level checks equivalent to the mortgage service's `ApplicationIn` schema. */
export function validateMortgageApplication(values: FormValues): Validated<MortgageApplicationInput> {
  const errors: FieldError[] = [];
  const property_value = readMoney(values, "property_value", "Property value", { min: 0n, minInclusive: false, max: DOLLARS(15_000_000) }, errors);
  const down_payment = readMoney(values, "down_payment", "Down payment", { min: 0n, minInclusive: true, max: DOLLARS(15_000_000) }, errors);
  const value: MortgageApplicationInput = {
    mortgage_type: "mortgage",
    property_value,
    down_payment,
    term_months: readInteger(values, "term_months", "Term", 1, 360, errors),
    annual_income: readMoney(values, "annual_income", "Annual income", { min: 0n, minInclusive: false, max: DOLLARS(100_000_000) }, errors),
    existing_monthly_debt: readMoney(values, "existing_monthly_debt", "Existing monthly debt", { min: 0n, minInclusive: true, max: DOLLARS(10_000_000) }, errors),
    credit_score: readInteger(values, "credit_score", "Credit score", 300, 850, errors),
  };
  if (!errors.some((e) => e.field === "property_value" || e.field === "down_payment") && toCents(down_payment) >= toCents(property_value)) {
    errors.push({ field: "down_payment", message: "Down payment must be less than the property value." });
  }
  return errors.length ? { ok: false, errors } : { ok: true, value };
}

function checkProduct(amount: Cents, termMonths: number, rules: ProductRules): RuleViolation | null {
  if (amount < toCents(rules.minimum_amount) || amount > toCents(rules.maximum_amount)) {
    return { status: 422, detail: "Amount is outside this product's advertised range" };
  }
  if (!rules.terms_months.includes(termMonths)) {
    return { status: 422, detail: "Choose a term advertised for this product" };
  }
  return null;
}

/** (existing debt + new payment) / (annual income / 12) > 40%, compared exactly in integers. */
export function exceedsDebtToIncome(existingMonthlyDebt: Cents, payment: Cents, annualIncome: Cents): boolean {
  return (existingMonthlyDebt + payment) * 12n * 100n > annualIncome * 40n;
}

/** Monthly debt-to-income ratio, for display only. */
export function debtToIncomeForDisplay(existingMonthlyDebt: Cents, payment: Cents, annualIncome: Cents): number {
  if (annualIncome <= 0n) return 0;
  return Number(((existingMonthlyDebt + payment) * 12n * 10_000n) / annualIncome) / 10_000;
}

export function decideLoan(input: LoanApplicationInput, rules: ProductRules): Decision | RuleViolation {
  const amount = toCents(input.amount);
  const violation = checkProduct(amount, input.term_months, rules);
  if (violation) return violation;
  const payment = monthlyPaymentCents(amount, rules.apr, input.term_months);
  let status: Decision["status"] = "approved";
  let decision_reason = "Meets the fictional score and debt-to-income rules";
  if (input.credit_score < 620) {
    status = "declined";
    decision_reason = "Mock credit score threshold is 620";
  } else if (exceedsDebtToIncome(toCents(input.existing_monthly_debt), payment, toCents(input.annual_income))) {
    status = "declined";
    decision_reason = "Mock monthly debt-to-income limit is 40%";
  }
  return { status, decision_reason, apr: rules.apr, monthly_payment: fromCents(payment) };
}

/** Financed amount and loan-to-value, as the mortgage service derives them. */
export function mortgageAmounts(propertyValue: string, downPayment: string): { amount: string; loan_to_value: string } {
  const property = toCents(propertyValue);
  const amount = property - toCents(downPayment);
  // Python's bare .quantize(Decimal("0.0001")) uses ROUND_HALF_EVEN.
  const ltv = property > 0n ? divRoundHalfEven(amount * 10_000n, property) : 0n;
  return { amount: fromCents(amount), loan_to_value: formatScaled({ units: ltv, scale: 4 }) };
}

export function decideMortgage(input: MortgageApplicationInput, rules: ProductRules): MortgageDecision | RuleViolation {
  const { amount, loan_to_value } = mortgageAmounts(input.property_value, input.down_payment);
  const amountCents = toCents(amount);
  const violation = checkProduct(amountCents, input.term_months, rules);
  if (violation) return violation;
  const payment = monthlyPaymentCents(amountCents, rules.apr, input.term_months);
  const property = toCents(input.property_value);
  let status: Decision["status"] = "approved";
  let decision_reason = "Meets the fictional score and debt-to-income rules";
  if (toCents(input.down_payment) * 100n < property * 5n) {
    status = "declined";
    decision_reason = "Mock minimum down payment is 5%";
  } else if (input.credit_score < 620) {
    status = "declined";
    decision_reason = "Mock credit score threshold is 620";
  } else if (exceedsDebtToIncome(toCents(input.existing_monthly_debt), payment, toCents(input.annual_income))) {
    status = "declined";
    decision_reason = "Mock monthly debt-to-income limit is 40%";
  }
  return { status, decision_reason, apr: rules.apr, monthly_payment: fromCents(payment), amount, loan_to_value };
}

export function isRuleViolation(value: Decision | RuleViolation): value is RuleViolation {
  return (value as RuleViolation).detail !== undefined && (value as RuleViolation).status === 422;
}

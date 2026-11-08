/**
 * mock_loan and mock_mortgage records in their exact JSON shapes.
 *
 * Offers copy each service's PRODUCTS table. Seeded applications are built by
 * the same rules the services apply (lib/finance/underwriting.ts), so their
 * APR, payment and decision are what the live service would return.
 */
import type { RawLender, RawLoanApplication, RawLoanOffer, RawMortgageApplication, RawMortgageOffer } from "../../types.ts";
import { decideLoan, decideMortgage, isRuleViolation, type LoanApplicationInput, type MortgageApplicationInput } from "../../finance/underwriting.ts";

export const LOAN_LENDER: RawLender = {
  id: "loans",
  name: "Capital Insight Mock Loans",
  loan_types: ["personal_loan", "auto_loan", "mortgage"],
  synthetic: true,
};

export const MORTGAGE_LENDER: RawLender = {
  id: "mortgages",
  name: "Capital Insight Mock Mortgages",
  mortgage_types: ["mortgage"],
  synthetic: true,
};

/** GET /v1/loan-offers (public). */
export const RAW_LOAN_OFFERS: readonly RawLoanOffer[] = [
  { loan_type: "personal_loan", name: "Mock Personal Loan", minimum_amount: "1000", maximum_amount: "50000", apr: "0.0990", terms_months: [12, 24, 36, 48, 60], currency: "USD", simulated: true },
  { loan_type: "auto_loan", name: "Mock Auto Loan", minimum_amount: "5000", maximum_amount: "80000", apr: "0.0650", terms_months: [24, 36, 48, 60, 72], currency: "USD", simulated: true },
  { loan_type: "mortgage", name: "Mock Mortgage", minimum_amount: "50000", maximum_amount: "750000", apr: "0.0625", terms_months: [180, 240, 360], currency: "USD", simulated: true },
];

/** GET /v1/mortgage-offers (public). */
export const RAW_MORTGAGE_OFFERS: readonly RawMortgageOffer[] = [
  { mortgage_type: "mortgage", name: "Mock Fixed-Rate Mortgage", minimum_amount: "50000", maximum_amount: "750000", apr: "0.0625", terms_months: [180, 240, 360], currency: "USD", simulated: true },
];

export function buildRawLoanApplication(
  input: LoanApplicationInput,
  meta: { id: string; customerId: string; createdAt: string },
): RawLoanApplication | null {
  const offer = RAW_LOAN_OFFERS.find((candidate) => candidate.loan_type === input.loan_type);
  if (!offer) return null;
  const decision = decideLoan(input, offer);
  if (isRuleViolation(decision)) return null;
  return {
    id: meta.id,
    customer_id: meta.customerId,
    loan_type: offer.loan_type,
    amount: input.amount,
    term_months: input.term_months,
    annual_income: input.annual_income,
    existing_monthly_debt: input.existing_monthly_debt,
    credit_score: input.credit_score,
    ...decision,
    created_at: meta.createdAt,
    simulated: true,
  };
}

export function buildRawMortgageApplication(
  input: MortgageApplicationInput,
  meta: { id: string; customerId: string; createdAt: string },
): RawMortgageApplication | null {
  const decision = decideMortgage(input, RAW_MORTGAGE_OFFERS[0]);
  if (isRuleViolation(decision)) return null;
  return {
    id: meta.id,
    customer_id: meta.customerId,
    mortgage_type: "mortgage",
    property_value: input.property_value,
    down_payment: input.down_payment,
    term_months: input.term_months,
    annual_income: input.annual_income,
    existing_monthly_debt: input.existing_monthly_debt,
    credit_score: input.credit_score,
    ...decision,
    created_at: meta.createdAt,
    simulated: true,
  };
}

function required<T>(value: T | null, label: string): T {
  if (value === null) throw new Error(`Fixture ${label} violates product rules`);
  return value;
}

/** Seeded history for customer1@loans.example.test: one active loan, one decline. */
export const SEEDED_LOAN_APPLICATIONS: readonly RawLoanApplication[] = [
  required(
    buildRawLoanApplication(
      { loan_type: "personal_loan", amount: "10000.00", term_months: 36, annual_income: "90000.00", existing_monthly_debt: "300.00", credit_score: 720 },
      { id: "loans-customer-001-personal_loan", customerId: "loans-customer-001", createdAt: "2025-11-01T00:00:00Z" },
    ),
    "personal loan",
  ),
  required(
    buildRawLoanApplication(
      { loan_type: "auto_loan", amount: "40000.00", term_months: 72, annual_income: "60000.00", existing_monthly_debt: "400.00", credit_score: 600 },
      { id: "5b7f3c1e-2a4d-4e8f-9c6b-1d0a2e3f4b5c", customerId: "loans-customer-001", createdAt: "2026-09-14T16:20:00Z" },
    ),
    "declined auto loan",
  ),
];

/** Seeded history for customer1@mortgages.example.test. */
export const SEEDED_MORTGAGE_APPLICATIONS: readonly RawMortgageApplication[] = [
  required(
    buildRawMortgageApplication(
      { mortgage_type: "mortgage", property_value: "350000.00", down_payment: "70000.00", term_months: 360, annual_income: "120000.00", existing_monthly_debt: "500.00", credit_score: 740 },
      { id: "mortgages-customer-001-mortgage", customerId: "mortgages-customer-001", createdAt: "2024-06-01T00:00:00Z" },
    ),
    "mortgage",
  ),
];

/**
 * Seeded records that get a fixture servicing snapshot on the dashboard.
 * Applications submitted during a demo session are never "funded".
 */
export const SERVICED_FIXTURE_IDS: ReadonlySet<string> = new Set([
  "loans-customer-001-personal_loan",
  "mortgages-customer-001-mortgage",
]);

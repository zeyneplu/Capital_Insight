/**
 * Run with `npm test` (Node's built-in test runner; Node 22.18+ strips types).
 * Golden files come from the real Python service code; regenerate them with
 * lib/finance/golden/generate_golden.py when service rules change.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { addMonthsClamped, buildSchedule, groupScheduleByLoanYear, monthlyPayment, summarizeSchedule, utcDateOf } from "./amortization.ts";
import { applyRate, divRoundHalfEven, divRoundHalfUp, fromCents, parseDecimal, ratioForDisplay, sumMoney, toCents } from "./money.ts";
import {
  decideLoan,
  decideMortgage,
  isRuleViolation,
  mortgageAmounts,
  validateLoanApplication,
  validateMortgageApplication,
  type ProductRules,
} from "./underwriting.ts";

interface GoldenRow {
  installment: number;
  due_date: string;
  payment: string;
  principal: string;
  interest: string;
  remaining_balance: string;
}
interface GoldenCase {
  input: Record<string, string | number>;
  error?: { status: number; detail: string };
  status?: "approved" | "declined";
  decision_reason?: string;
  apr?: string;
  monthly_payment?: string;
  amount?: string;
  loan_to_value?: string;
  schedule_len?: number;
  schedule_sample?: GoldenRow[];
  total_interest?: string;
}

const readGolden = (name: string): GoldenCase[] =>
  JSON.parse(readFileSync(new URL(`./golden/${name}.json`, import.meta.url), "utf8"));

/** Product rules copied from the services' PRODUCTS tables. */
const LOAN_PRODUCTS: Record<string, ProductRules> = {
  personal_loan: { minimum_amount: "1000", maximum_amount: "50000", apr: "0.0990", terms_months: [12, 24, 36, 48, 60] },
  auto_loan: { minimum_amount: "5000", maximum_amount: "80000", apr: "0.0650", terms_months: [24, 36, 48, 60, 72] },
  mortgage: { minimum_amount: "50000", maximum_amount: "750000", apr: "0.0625", terms_months: [180, 240, 360] },
};
const MORTGAGE_PRODUCT: ProductRules = { minimum_amount: "50000", maximum_amount: "750000", apr: "0.0625", terms_months: [180, 240, 360] };
const GOLDEN_CREATED_AT = "2024-01-31T15:00:00Z";

const asForm = (input: Record<string, string | number>) =>
  Object.fromEntries(Object.entries(input).map(([key, value]) => [key, String(value)]));

function checkSchedule(golden: GoldenCase, amount: string) {
  const rows = buildSchedule({
    amount,
    apr: golden.apr!,
    monthlyPayment: golden.monthly_payment!,
    termMonths: Number(golden.input.term_months),
    createdAt: GOLDEN_CREATED_AT,
  });
  assert.equal(rows.length, golden.schedule_len);
  assert.deepEqual([...rows.slice(0, 3), ...rows.slice(-2)], golden.schedule_sample);
  assert.equal(rows.at(-1)!.remaining_balance, "0.00");
  assert.equal(summarizeSchedule(rows).totalInterest, golden.total_interest);
  assert.equal(summarizeSchedule(rows).totalPrincipal, fromCents(toCents(amount)));
}

test("money parsing and formatting round-trips exactly", () => {
  assert.equal(toCents("16487.05"), 1648705n);
  assert.equal(toCents("0.1") + toCents("0.2"), toCents("0.3"));
  assert.equal(fromCents(-5n), "-0.05");
  assert.equal(sumMoney(["0.10", "0.20", "1000000.70"]), "1000001.00");
  assert.throws(() => toCents("1.234"));
  assert.throws(() => toCents("1e3"));
  assert.deepEqual(parseDecimal("0.0625"), { units: 625n, scale: 4 });
});

test("rounding helpers match Python ROUND_HALF_UP and ROUND_HALF_EVEN", () => {
  assert.equal(divRoundHalfUp(5n, 2n), 3n);
  assert.equal(divRoundHalfUp(-5n, 2n), -3n);
  assert.equal(divRoundHalfUp(7n, 3n), 2n);
  assert.equal(divRoundHalfEven(5n, 2n), 2n);
  assert.equal(divRoundHalfEven(7n, 2n), 4n);
  // One month of interest on $10,000 at 9.90% APR is $82.50.
  assert.equal(applyRate(toCents("10000.00"), "0.0990", 12n), toCents("82.50"));
  assert.equal(ratioForDisplay(toCents("600"), toCents("5000")), 0.12);
});

test("month arithmetic clamps to month length", () => {
  assert.equal(addMonthsClamped("2024-01-31", 1), "2024-02-29");
  assert.equal(addMonthsClamped("2025-01-31", 1), "2025-02-28");
  assert.equal(addMonthsClamped("2026-11-30", 3), "2027-02-28");
  assert.equal(addMonthsClamped("2026-12-15", 1), "2027-01-15");
  assert.equal(utcDateOf("2026-11-01T23:30:00-05:00"), "2026-11-02");
});

test("monthly payment matches the services' Decimal implementation", () => {
  assert.equal(monthlyPayment("280000.00", "0.0625", 360), "1724.01");
  assert.equal(monthlyPayment("1200.00", "0", 12), "100.00");
});

for (const golden of readGolden("loan")) {
  test(`loan golden: ${JSON.stringify(golden.input)}`, () => {
    const validated = validateLoanApplication(asForm(golden.input), Object.keys(LOAN_PRODUCTS));
    assert.ok(validated.ok, "golden inputs pass schema validation");
    const result = decideLoan(validated.value, LOAN_PRODUCTS[validated.value.loan_type]);
    if (golden.error) {
      assert.ok(isRuleViolation(result));
      assert.deepEqual(result, { status: 422, detail: golden.error.detail });
      return;
    }
    assert.ok(!isRuleViolation(result));
    assert.equal(result.status, golden.status);
    assert.equal(result.decision_reason, golden.decision_reason);
    assert.equal(result.monthly_payment, golden.monthly_payment);
    checkSchedule(golden, validated.value.amount);
  });
}

for (const golden of readGolden("mortgage")) {
  test(`mortgage golden: ${JSON.stringify(golden.input)}`, () => {
    const validated = validateMortgageApplication(asForm(golden.input));
    assert.ok(validated.ok, "golden inputs pass schema validation");
    const result = decideMortgage(validated.value, MORTGAGE_PRODUCT);
    if (golden.error) {
      assert.ok(isRuleViolation(result));
      assert.equal(result.detail, golden.error.detail);
      return;
    }
    assert.ok(!isRuleViolation(result));
    assert.equal(result.status, golden.status);
    assert.equal(result.decision_reason, golden.decision_reason);
    assert.equal(result.amount, golden.amount);
    assert.equal(result.loan_to_value, golden.loan_to_value);
    assert.equal(result.monthly_payment, golden.monthly_payment);
    checkSchedule(golden, result.amount);
  });
}

test("schema validation reports field errors like a FastAPI 422", () => {
  const loan = validateLoanApplication(
    { loan_type: "boat", amount: "12.345", term_months: "3.5", annual_income: "0", existing_monthly_debt: "-1", credit_score: "900" },
    Object.keys(LOAN_PRODUCTS),
  );
  assert.ok(!loan.ok);
  assert.deepEqual(
    loan.errors.map((e) => e.field),
    ["loan_type", "amount", "term_months", "annual_income", "existing_monthly_debt", "credit_score"],
  );
  const mortgage = validateMortgageApplication({
    property_value: "300000", down_payment: "300000", term_months: "360", annual_income: "100000", existing_monthly_debt: "0", credit_score: "700",
  });
  assert.ok(!mortgage.ok);
  assert.equal(mortgage.errors[0].field, "down_payment");
});

test("thousands separators are accepted in form input", () => {
  const result = validateMortgageApplication({
    property_value: "350,000", down_payment: "70,000.00", term_months: "360", annual_income: "120,000", existing_monthly_debt: "500", credit_score: "740",
  });
  assert.ok(result.ok);
  assert.equal(result.value.property_value, "350000.00");
  assert.deepEqual(mortgageAmounts(result.value.property_value, result.value.down_payment), { amount: "280000.00", loan_to_value: "0.8000" });
});

test("yearly grouping preserves totals", () => {
  const rows = buildSchedule({ amount: "10000.00", apr: "0.0990", monthlyPayment: "322.20", termMonths: 36, createdAt: GOLDEN_CREATED_AT });
  const years = groupScheduleByLoanYear(rows);
  assert.equal(years.length, 3);
  assert.equal(sumMoney(years.map((y) => y.principal)), "10000.00");
  assert.equal(years[2].endingBalance, "0.00");
});

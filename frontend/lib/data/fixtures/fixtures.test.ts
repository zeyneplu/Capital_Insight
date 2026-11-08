/** Invariants that keep the demo portfolio internally consistent. Run with `npm test`. */
import { test } from "node:test";
import assert from "node:assert/strict";
import { RAW_ACCOUNTS, RAW_TRANSACTIONS, FIXTURE_WINDOW } from "./bank.ts";
import { INSTITUTIONS, SNAPSHOT_DATE } from "./institutions.ts";
import { SEEDED_LOAN_APPLICATIONS, SEEDED_MORTGAGE_APPLICATIONS } from "./lending.ts";
import { normalizeAccount, normalizeLoanApplication, normalizeMortgageApplication, normalizeTransaction } from "../normalize.ts";
import { buildDashboard, servicingSnapshotFor } from "../../finance/portfolio.ts";
import { buildSchedule } from "../../finance/amortization.ts";
import { fromCents, sumMoney, toCents } from "../../finance/money.ts";

const institution = (id: string) => {
  const found = INSTITUTIONS.find((candidate) => candidate.id === id)!;
  return { id: found.id, name: found.name, service: found.service };
};

test("every balance equals opening balance plus its transactions", () => {
  for (const raw of RAW_ACCOUNTS) {
    const account = normalizeAccount(raw, institution(raw.institution_id));
    const transactions = (RAW_TRANSACTIONS.get(raw.id) ?? []).map((t) => normalizeTransaction(t, account));
    let balance = toCents(raw.opening_balance);
    for (const transaction of transactions) {
      balance += (transaction.balanceEffect === "increase" ? 1n : -1n) * toCents(transaction.amount);
    }
    assert.equal(fromCents(balance), raw.balance, raw.id);
  }
});

test("asset accounts never overdraw and cards stay within limits on any day", () => {
  for (const raw of RAW_ACCOUNTS) {
    const account = normalizeAccount(raw, institution(raw.institution_id));
    const chronological = [...(RAW_TRANSACTIONS.get(raw.id) ?? [])].reverse();
    let balance = toCents(raw.opening_balance);
    for (const t of chronological) {
      balance += (normalizeTransaction(t, account).balanceEffect === "increase" ? 1n : -1n) * toCents(t.amount);
      assert.ok(balance >= 0n, `${raw.id} negative on ${t.transaction_date}`);
      if (raw.credit_limit) assert.ok(balance <= toCents(raw.credit_limit), `${raw.id} over limit`);
    }
  }
});

test("IDs are unique and dates stay inside the fixture window", () => {
  const ids = new Set<string>();
  for (const transactions of RAW_TRANSACTIONS.values()) {
    for (const t of transactions) {
      assert.ok(!ids.has(t.id), `duplicate ${t.id}`);
      ids.add(t.id);
      assert.ok(t.transaction_date >= FIXTURE_WINDOW.start && t.transaction_date <= FIXTURE_WINDOW.end);
      assert.ok(toCents(t.amount) > 0n);
    }
  }
  // Account pages show 10 rows per page; these accounts must span several pages.
  assert.ok(RAW_TRANSACTIONS.get("chase-customer-001-checking")!.length > 30);
  assert.ok(RAW_TRANSACTIONS.get("chase-customer-001-credit_card")!.length > 30);
  // ...and some accounts must have none, to exercise the empty state.
  assert.equal(RAW_TRANSACTIONS.get("pnc-customer-001-cd")!.length, 0);
});

test("portfolio has no bank mortgage account (the mortgage lives at mock_mortgage)", () => {
  assert.ok(!RAW_ACCOUNTS.some((account) => account.account_type === "mortgage"));
});

test("seeded lender records have the intended decisions", () => {
  assert.deepEqual(SEEDED_LOAN_APPLICATIONS.map((a) => a.status), ["approved", "declined"]);
  assert.equal(SEEDED_MORTGAGE_APPLICATIONS[0].monthly_payment, "1724.01");
});

test("dashboard totals reconcile with their parts", () => {
  const accounts = RAW_ACCOUNTS.map((raw) => normalizeAccount(raw, institution(raw.institution_id)));
  const transactions = accounts.flatMap((account) => (RAW_TRANSACTIONS.get(account.id) ?? []).map((t) => normalizeTransaction(t, account)));
  const service = (raw: { amount: string; apr: string; monthly_payment: string; term_months: number; created_at: string }) =>
    servicingSnapshotFor(
      buildSchedule({ amount: raw.amount, apr: raw.apr, monthlyPayment: raw.monthly_payment, termMonths: raw.term_months, createdAt: raw.created_at }),
      SNAPSHOT_DATE,
      raw.amount,
    );
  const loans = SEEDED_LOAN_APPLICATIONS.map((raw) =>
    normalizeLoanApplication(raw, { lender: institution("loans"), submittedThisSession: false, servicing: raw.status === "approved" ? service(raw) : null }),
  );
  const mortgages = SEEDED_MORTGAGE_APPLICATIONS.map((raw) =>
    normalizeMortgageApplication(raw, { lender: institution("mortgages"), submittedThisSession: false, servicing: service(raw) }),
  );
  const dashboard = buildDashboard({
    snapshotDate: SNAPSHOT_DATE,
    accounts,
    transactions,
    loans,
    mortgages,
    connectedInstitutions: [],
    availableInstitutions: [],
  });
  assert.equal(dashboard.totals.assets, sumMoney(dashboard.assets.map((i) => i.amount)));
  assert.equal(dashboard.totals.liabilities, sumMoney(dashboard.liabilities.map((i) => i.amount)));
  assert.equal(fromCents(toCents(dashboard.totals.assets) - toCents(dashboard.totals.liabilities)), dashboard.totals.netWorth);
  assert.equal(dashboard.spending.total, sumMoney(dashboard.spending.byCategory.map((c) => c.amount)));
  assert.ok(!dashboard.spending.byCategory.some((c) => ["salary", "transfers", "debt_payment"].includes(c.category)));
  // Personal loan: 12 installments (Dec 2025 - Nov 2026) assumed paid as of the snapshot.
  assert.equal(loans[0].servicing?.installmentsAssumedPaid, 12);
  assert.equal(loans[0].servicing?.nextDueDate, "2026-12-01");
  // The declined application contributes nothing.
  assert.ok(!dashboard.liabilities.some((item) => item.id === loans[1].id));
  // Obligations never include dates before the snapshot (nothing presented as overdue).
  assert.ok(dashboard.obligations.every((o) => o.dueDate === null || o.dueDate > SNAPSHOT_DATE));
});

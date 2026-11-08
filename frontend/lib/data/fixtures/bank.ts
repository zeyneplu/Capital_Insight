/**
 * Deterministic mock_bank records in the exact `AccountOut` / `TransactionOut`
 * JSON shape, for the window 2026-08-03 .. 2026-11-01 (90 days, like seed.py).
 *
 * Balances are never typed in by hand: every account starts from its
 * `opening_balance` and the ledger below applies each transaction, using the
 * services' rule (assets: credit +, debit -; liabilities: debit +, credit -).
 * A seeded PRNG keeps amounts stable across runs and machines.
 *
 * Portfolio choices that avoid double counting:
 *  - Bank-held loans (PNC auto loan, Discover personal loan) are real account
 *    balances from mock_bank.
 *  - The mock_loan personal loan and the mock_mortgage mortgage are separate
 *    lender records (see lending.ts); no bank mortgage account is included.
 */
import type { AccountType, IsoDate, RawAccount, RawTransaction, TransactionCategory } from "../../types.ts";
import { applyRate, divRoundHalfEven, fromCents, maxCents, toCents, type Cents } from "../../finance/money.ts";
import { SNAPSHOT_DATE, SNAPSHOT_TIMESTAMP } from "./institutions.ts";

export const WINDOW_START: IsoDate = "2026-08-03";
const WINDOW_DAYS = 90;
const LIABILITY_TYPES = new Set<AccountType>(["credit_card", "personal_loan", "auto_loan", "mortgage"]);

/** mulberry32: tiny, fast, deterministic PRNG. */
function createRng(seed: number) {
  let state = seed >>> 0;
  const next = () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    chance: (probability: number) => next() < probability,
    /** Whole cents between min and max dollars, inclusive. */
    cents: (minDollars: number, maxDollars: number): Cents =>
      BigInt(Math.floor(minDollars * 100 + next() * (maxDollars - minDollars) * 100)),
    pick: <T>(items: readonly T[]): T => items[Math.floor(next() * items.length)],
  };
}

function dateAt(day: number): IsoDate {
  const date = new Date(`${WINDOW_START}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + day);
  return date.toISOString().slice(0, 10);
}

type AccountSpec = Omit<RawAccount, "balance" | "currency" | "created_at" | "updated_at" | "customer_id" | "minimum_payment" | "outstanding_principal" | "account_name"> &
  Partial<Pick<RawAccount, "minimum_payment" | "outstanding_principal">> & { bankName: string };

const NULL_DETAILS = {
  apy: null,
  credit_limit: null,
  purchase_apr: null,
  payment_due_date: null,
  original_principal: null,
  apr: null,
  monthly_payment: null,
  term_months: null,
  maturity_date: null,
  account_value: null,
  account_subtype: null,
} as const;

const titleCase = (type: AccountType) =>
  type.split("_").map((word) => (word === "ira" || word === "cd" ? word.toUpperCase() : word[0].toUpperCase() + word.slice(1))).join(" ");

const SPECS: AccountSpec[] = [
  { ...NULL_DETAILS, id: "chase-customer-001-checking", institution_id: "chase", bankName: "Chase Mock Bank", account_type: "checking", account_number_last4: "4821", opening_balance: "4200.00", apy: "0.0005" },
  { ...NULL_DETAILS, id: "chase-customer-001-savings", institution_id: "chase", bankName: "Chase Mock Bank", account_type: "savings", account_number_last4: "7710", opening_balance: "12500.00", apy: "0.0410" },
  { ...NULL_DETAILS, id: "chase-customer-001-credit_card", institution_id: "chase", bankName: "Chase Mock Bank", account_type: "credit_card", account_number_last4: "3307", opening_balance: "1000.00", credit_limit: "8000.00", purchase_apr: "0.2299", payment_due_date: "2026-11-21" },
  { ...NULL_DETAILS, id: "amex-customer-001-credit_card", institution_id: "amex", bankName: "American Express Mock Bank", account_type: "credit_card", account_number_last4: "1009", opening_balance: "640.00", credit_limit: "12000.00", purchase_apr: "0.2149", payment_due_date: "2026-11-21" },
  { ...NULL_DETAILS, id: "amex-customer-001-savings", institution_id: "amex", bankName: "American Express Mock Bank", account_type: "savings", account_number_last4: "5532", opening_balance: "6000.00", apy: "0.0390" },
  { ...NULL_DETAILS, id: "pnc-customer-001-cd", institution_id: "pnc", bankName: "PNC Mock Bank", account_type: "cd", account_number_last4: "9046", opening_balance: "10000.00", apy: "0.0410", maturity_date: "2027-11-01" },
  { ...NULL_DETAILS, id: "pnc-customer-001-ira", institution_id: "pnc", bankName: "PNC Mock Bank", account_type: "ira", account_number_last4: "6618", opening_balance: "18400.00", account_value: "18400.00", account_subtype: "roth" },
  { ...NULL_DETAILS, id: "pnc-customer-001-auto_loan", institution_id: "pnc", bankName: "PNC Mock Bank", account_type: "auto_loan", account_number_last4: "2275", opening_balance: "15340.00", original_principal: "24000.00", apr: "0.0589", monthly_payment: "465.00", term_months: 60 },
  { ...NULL_DETAILS, id: "discover-customer-001-credit_card", institution_id: "discover", bankName: "Discover Mock Bank", account_type: "credit_card", account_number_last4: "8150", opening_balance: "300.00", credit_limit: "6000.00", purchase_apr: "0.2499", payment_due_date: "2026-11-21" },
  { ...NULL_DETAILS, id: "discover-customer-001-personal_loan", institution_id: "discover", bankName: "Discover Mock Bank", account_type: "personal_loan", account_number_last4: "4402", opening_balance: "6120.00", original_principal: "9000.00", apr: "0.1149", monthly_payment: "260.00", term_months: 36 },
  { ...NULL_DETAILS, id: "discover-customer-001-savings", institution_id: "discover", bankName: "Discover Mock Bank", account_type: "savings", account_number_last4: "3391", opening_balance: "2500.00", apy: "0.0375" },
];

const CARD_SPENDING: Record<string, readonly [TransactionCategory, string, number, number][]> = {
  "chase-customer-001-credit_card": [
    ["dining", "Fictional Cafe", 8, 48],
    ["dining", "Sample Noodle Bar", 12, 65],
    ["groceries", "Demo Market", 20, 95],
    ["shopping", "Sample Store", 15, 140],
    ["transportation", "Demo Transit", 3, 28],
    ["entertainment", "Sample Cinema", 12, 45],
  ],
  "amex-customer-001-credit_card": [
    ["shopping", "Example Outfitters", 40, 220],
    ["dining", "Fictional Bistro", 35, 120],
    ["entertainment", "Sample Streaming", 11, 23],
    ["education", "Example Books", 15, 80],
    ["healthcare", "Demo Pharmacy", 10, 60],
  ],
  "discover-customer-001-credit_card": [
    ["transportation", "Demo Fuel", 30, 65],
    ["shopping", "Sample Hardware", 15, 90],
    ["other", "Sample Services", 10, 50],
  ],
};

interface LedgerAccount {
  spec: AccountSpec;
  liability: boolean;
  balance: Cents;
  transactions: RawTransaction[];
}

function buildLedger() {
  const rng = createRng(20261101);
  const ledger = new Map<string, LedgerAccount>(
    SPECS.map((spec) => [spec.id, { spec, liability: LIABILITY_TYPES.has(spec.account_type), balance: toCents(spec.opening_balance), transactions: [] }]),
  );

  const post = (
    accountId: string,
    day: number,
    amount: Cents,
    direction: "credit" | "debit",
    category: TransactionCategory,
    merchant: string,
    description: string,
  ) => {
    if (amount <= 0n) return;
    const account = ledger.get(accountId)!;
    const sign = (direction === "credit" ? 1n : -1n) * (account.liability ? -1n : 1n);
    account.balance += sign * amount;
    const date = dateAt(day);
    const sequence = String(account.transactions.length + 1).padStart(3, "0");
    account.transactions.push({
      id: `${accountId}-tx-${date}-${sequence}`,
      account_id: accountId,
      transaction_date: date,
      description,
      merchant,
      category,
      amount: fromCents(amount),
      direction,
      transaction_type: category === "debt_payment" ? "payment" : category === "salary" || category === "transfers" ? "transfer" : "purchase",
      created_at: `${date}T12:00:00Z`,
    });
  };

  /** Pays a card or loan from checking: two linked entries, one per account. */
  const payFromChecking = (day: number, target: string, amount: Cents, label: string) => {
    post("chase-customer-001-checking", day, amount, "debit", "debt_payment", label, `Payment to ${label}`);
    post(target, day, amount, "credit", "debt_payment", "Payment received", "Payment received - thank you");
  };

  for (let day = 0; day <= WINDOW_DAYS; day += 1) {
    const date = dateAt(day);
    const dayOfMonth = Number(date.slice(8, 10));

    // Checking: income, housing, bills and payments
    if ((day - 4) % 14 === 0 && day >= 4) {
      post("chase-customer-001-checking", day, toCents("2450.00"), "credit", "salary", "Example Employer", "Payroll deposit - Example Employer");
    }
    if (dayOfMonth === 1) post("chase-customer-001-checking", day, toCents("1650.00"), "debit", "rent", "Fictional Housing", "Monthly rent - Fictional Housing");
    if (dayOfMonth === 5) payFromChecking(day, "pnc-customer-001-auto_loan", toCents("465.00"), "PNC auto loan");
    if (dayOfMonth === 10) payFromChecking(day, "discover-customer-001-personal_loan", toCents("260.00"), "Discover personal loan");
    if (dayOfMonth === 12) post("chase-customer-001-checking", day, rng.cents(85, 140), "debit", "utilities", "Example Energy", "Electric and gas - Example Energy");
    if (dayOfMonth === 20) post("chase-customer-001-checking", day, toCents("65.00"), "debit", "utilities", "Sample Fiber", "Home internet - Sample Fiber");
    if (dayOfMonth === 15) {
      post("chase-customer-001-checking", day, toCents("300.00"), "debit", "transfers", "Chase savings", "Transfer to Chase savings");
      post("chase-customer-001-savings", day, toCents("300.00"), "credit", "transfers", "Chase checking", "Transfer from Chase checking");
    }
    if (day % 7 === 5) post("chase-customer-001-checking", day, rng.cents(55, 140), "debit", "groceries", "Demo Market", "Weekly groceries - Demo Market");
    if (rng.chance(0.06)) post("chase-customer-001-checking", day, rng.cents(20, 90), "debit", "healthcare", "Demo Clinic", "Copay - Demo Clinic");

    // Card purchases
    for (const [cardId, merchants] of Object.entries(CARD_SPENDING)) {
      const probability = cardId.startsWith("chase") ? 0.6 : cardId.startsWith("amex") ? 0.25 : 0.12;
      if (rng.chance(probability)) {
        const [category, merchant, min, max] = rng.pick(merchants);
        post(cardId, day, rng.cents(min, max), "debit", category, merchant, `${merchant}`);
      }
    }

    // Card payments in full from checking
    if (dayOfMonth === 18) payFromChecking(day, "chase-customer-001-credit_card", ledger.get("chase-customer-001-credit_card")!.balance, "Chase card");
    if (dayOfMonth === 22) payFromChecking(day, "amex-customer-001-credit_card", ledger.get("amex-customer-001-credit_card")!.balance, "Amex card");
    if (dayOfMonth === 25) payFromChecking(day, "discover-customer-001-credit_card", ledger.get("discover-customer-001-credit_card")!.balance, "Discover card");

    // Monthly savings interest, at each account's APY
    if (dayOfMonth === 28) {
      for (const id of ["chase-customer-001-savings", "amex-customer-001-savings", "discover-customer-001-savings"]) {
        const account = ledger.get(id)!;
        post(id, day, applyRate(account.balance, account.spec.apy!, 12n), "credit", "other", "Interest", "Interest paid");
      }
    }
  }
  return ledger;
}

function toRawAccount({ spec, liability, balance }: LedgerAccount): RawAccount {
  const { bankName, ...fields } = spec;
  const raw: RawAccount = {
    ...fields,
    customer_id: `${spec.institution_id}-customer-001`,
    account_name: `${bankName} ${titleCase(spec.account_type)}`,
    currency: "USD",
    balance: fromCents(balance),
    created_at: `${WINDOW_START}T00:00:00Z`,
    updated_at: SNAPSHOT_TIMESTAMP,
    minimum_payment: null,
    outstanding_principal: null,
  };
  if (spec.account_type === "credit_card") {
    // seed.py: max(25, 2% of balance), quantized with the default (half-even) context.
    raw.minimum_payment = fromCents(maxCents(2500n, divRoundHalfEven(balance * 2n, 100n)));
  } else if (liability) {
    raw.outstanding_principal = fromCents(balance);
  }
  if (spec.account_type === "ira") raw.account_value = fromCents(balance);
  return raw;
}

const LEDGER = buildLedger();

export const RAW_ACCOUNTS: readonly RawAccount[] = [...LEDGER.values()].map(toRawAccount);

/** All transactions by account, newest first (date desc, id desc), as the service orders them. */
export const RAW_TRANSACTIONS: ReadonlyMap<string, readonly RawTransaction[]> = new Map(
  [...LEDGER.entries()].map(([id, account]) => [
    id,
    [...account.transactions].sort((a, b) =>
      a.transaction_date === b.transaction_date ? (a.id < b.id ? 1 : -1) : a.transaction_date < b.transaction_date ? 1 : -1,
    ),
  ]),
);

export const FIXTURE_WINDOW = { start: WINDOW_START, end: SNAPSHOT_DATE } as const;

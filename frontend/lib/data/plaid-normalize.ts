import type { Account, AccountType, InstitutionSummary, Transaction, TransactionCategory } from "../types.ts";
import { parseDecimal, divRoundHalfUp, fromCents, pow10 } from "../finance/money.ts";

/** Plaid may return sub-cent precision. Keep the API value intact; round UI money exactly. */
function portfolioMoney(value: string): string {
  const {units, scale} = parseDecimal(value);
  return fromCents(divRoundHalfUp(units * 100n, pow10(scale)));
}

export interface PlaidAccountSnapshot {
  id: string;
  connection_id: string;
  source_account_id: string;
  source_account_type?: string;
  account_type: string;
  account_name: string;
  account_number_last4?: string | null;
  currency: string | null;
  balance: string | null;
  balance_kind: "asset" | "liability" | "unknown";
  balance_as_of?: string | null;
}

/** The common portfolio totals USD balances. Full snapshots remain visible on /banks. */
export function normalizePlaidAccount(raw: PlaidAccountSnapshot, institution: InstitutionSummary, fetchedAt: string): Account | null {
  if (raw.balance === null || raw.currency !== "USD" || raw.balance_kind === "unknown") return null;
  const types: Record<string, AccountType> = {
    checking: "checking", savings: "savings", money_market: "savings", cd: "cd",
    credit_card: "credit_card", mortgage: "mortgage", auto: "auto_loan", personal: "personal_loan",
    ira: "ira", roth: "ira", roth_401k: "investment", "401k": "investment",
  };
  const type = types[raw.account_type] ?? (raw.balance_kind === "liability" ? "other_liability" : raw.source_account_type === "investment" ? "investment" : "other_asset");
  return {
    id: raw.id,
    source: {service: "plaid", institutionId: institution.id, recordId: raw.source_account_id},
    institution, type, classification: raw.balance_kind, name: raw.account_name,
    last4: raw.account_number_last4 ?? "", currency: raw.currency, balance: portfolioMoney(raw.balance),
    openingBalance: null, createdAt: fetchedAt, updatedAt: raw.balance_as_of ?? fetchedAt,
    details: {
      apy: null, creditLimit: null, purchaseApr: null, minimumPayment: null, paymentDueDate: null,
      originalPrincipal: null, outstandingPrincipal: null, apr: null, monthlyPayment: null,
      termMonths: null, maturityDate: null, accountValue: null, subtype: raw.account_type,
    },
  };
}

export interface PlaidTransactionSnapshot {
  id:string; account_id:string; transaction_date:string; description:string; merchant:string|null;
  category:string; amount:string; direction:"credit"|"debit";
}

export function normalizePlaidTransaction(raw: PlaidTransactionSnapshot, account: Account): Transaction {
  const categories: Record<string, TransactionCategory> = {
    food_and_drink:"dining", general_merchandise:"shopping", transportation:"transportation",
    travel:"transportation", rent_and_utilities:"utilities", entertainment:"entertainment",
    medical:"healthcare", income:"salary", loan_payments:"debt_payment",
    transfer_in:"transfers", transfer_out:"transfers", home_improvement:"shopping",
  };
  return {
    id:raw.id, source:{service:"plaid",institutionId:account.institution.id,recordId:raw.id},
    accountId:account.id, date:raw.transaction_date, description:raw.description, merchant:raw.merchant ?? "",
    category:categories[raw.category] ?? "other", amount:portfolioMoney(raw.amount), direction:raw.direction, type:"plaid",
    balanceEffect:(account.classification === "asset") === (raw.direction === "credit") ? "increase" : "decrease",
  };
}

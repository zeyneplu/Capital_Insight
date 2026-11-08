/**
 * Raw service JSON -> view models. Both the fixture provider and any future
 * HTTP provider must go through these functions, so pages never see a raw
 * service shape and switching providers does not change page code.
 */
import type {
  Account,
  AccountType,
  BalanceClass,
  InstitutionSummary,
  LoanApplication,
  LoanOffer,
  MortgageApplication,
  RawAccount,
  RawLoanApplication,
  RawLoanOffer,
  RawMortgageApplication,
  RawMortgageOffer,
  RawTransaction,
  ServicingSnapshot,
  Transaction,
} from "../types.ts";

const LIABILITY_TYPES: ReadonlySet<AccountType> = new Set(["credit_card", "personal_loan", "auto_loan", "mortgage"]);

export function classifyAccount(type: AccountType): BalanceClass {
  return LIABILITY_TYPES.has(type) ? "liability" : "asset";
}

export function normalizeAccount(raw: RawAccount, institution: InstitutionSummary): Account {
  if (raw.institution_id !== institution.id) {
    throw new Error(`Account ${raw.id} belongs to ${raw.institution_id}, not ${institution.id}`);
  }
  return {
    id: raw.id,
    source: { service: institution.service, institutionId: institution.id, recordId: raw.id },
    institution,
    type: raw.account_type,
    classification: classifyAccount(raw.account_type),
    name: raw.account_name,
    last4: raw.account_number_last4,
    currency: raw.currency,
    balance: raw.balance,
    openingBalance: raw.opening_balance,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    details: {
      apy: raw.apy,
      creditLimit: raw.credit_limit,
      purchaseApr: raw.purchase_apr,
      minimumPayment: raw.minimum_payment,
      paymentDueDate: raw.payment_due_date,
      originalPrincipal: raw.original_principal,
      outstandingPrincipal: raw.outstanding_principal,
      apr: raw.apr,
      monthlyPayment: raw.monthly_payment,
      termMonths: raw.term_months,
      maturityDate: raw.maturity_date,
      accountValue: raw.account_value,
      subtype: raw.account_subtype,
    },
  };
}

export function normalizeTransaction(raw: RawTransaction, account: Pick<Account, "id" | "classification" | "institution">): Transaction {
  const increasesAsset = raw.direction === "credit";
  const increases = account.classification === "asset" ? increasesAsset : !increasesAsset;
  return {
    id: raw.id,
    source: { service: account.institution.service, institutionId: account.institution.id, recordId: raw.id },
    accountId: raw.account_id,
    date: raw.transaction_date,
    description: raw.description,
    merchant: raw.merchant,
    category: raw.category,
    amount: raw.amount,
    direction: raw.direction,
    type: raw.transaction_type,
    balanceEffect: increases ? "increase" : "decrease",
  };
}

export function normalizeLoanOffer(raw: RawLoanOffer | RawMortgageOffer): LoanOffer {
  return {
    loanType: "loan_type" in raw ? raw.loan_type : "mortgage",
    name: raw.name,
    minimumAmount: raw.minimum_amount,
    maximumAmount: raw.maximum_amount,
    apr: raw.apr,
    termsMonths: [...raw.terms_months],
    currency: raw.currency,
    simulated: raw.simulated,
  };
}

interface ApplicationContext {
  lender: InstitutionSummary;
  submittedThisSession: boolean;
  servicing: ServicingSnapshot | null;
}

export function normalizeLoanApplication(raw: RawLoanApplication, context: ApplicationContext): LoanApplication {
  return {
    kind: "loan",
    id: raw.id,
    source: { service: context.lender.service, institutionId: context.lender.id, recordId: raw.id },
    lender: context.lender,
    loanType: raw.loan_type,
    amount: raw.amount,
    termMonths: raw.term_months,
    apr: raw.apr,
    monthlyPayment: raw.monthly_payment,
    status: raw.status,
    decisionReason: raw.decision_reason,
    createdAt: raw.created_at,
    applicant: { annualIncome: raw.annual_income, existingMonthlyDebt: raw.existing_monthly_debt, creditScore: raw.credit_score },
    submittedThisSession: context.submittedThisSession,
    servicing: context.servicing,
  };
}

export function normalizeMortgageApplication(raw: RawMortgageApplication, context: ApplicationContext): MortgageApplication {
  return {
    kind: "mortgage",
    id: raw.id,
    source: { service: context.lender.service, institutionId: context.lender.id, recordId: raw.id },
    lender: context.lender,
    amount: raw.amount,
    propertyValue: raw.property_value,
    downPayment: raw.down_payment,
    loanToValue: raw.loan_to_value,
    termMonths: raw.term_months,
    apr: raw.apr,
    monthlyPayment: raw.monthly_payment,
    status: raw.status,
    decisionReason: raw.decision_reason,
    createdAt: raw.created_at,
    applicant: { annualIncome: raw.annual_income, existingMonthlyDebt: raw.existing_monthly_debt, creditScore: raw.credit_score },
    submittedThisSession: context.submittedThisSession,
    servicing: context.servicing,
  };
}

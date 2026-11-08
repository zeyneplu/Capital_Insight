import type { AccountType, TransactionOperation } from "../types.ts";

export const TRANSACTION_LABELS: Record<TransactionOperation,string> = {
  deposit:"Deposit", withdrawal:"Cash withdrawal", salary:"Salary / paycheck", purchase:"Purchase",
  payment:"Bill payment", refund:"Refund", transfer:"Transfer to another account",
  card_payment:"Pay this credit card", loan_payment:"Pay loan principal", interest:"Interest", fee:"Fee",
};

export function transactionOperations(type: AccountType): TransactionOperation[] {
  if (type === "checking" || type === "savings") return ["deposit","salary","purchase","payment","withdrawal","transfer","refund","interest","fee"];
  if (type === "credit_card") return ["purchase","card_payment","refund","fee","interest"];
  if (["personal_loan","auto_loan","mortgage"].includes(type)) return ["loan_payment"];
  return [];
}

export function pairedOperation(operation: TransactionOperation) {
  return ["transfer","card_payment","loan_payment"].includes(operation);
}

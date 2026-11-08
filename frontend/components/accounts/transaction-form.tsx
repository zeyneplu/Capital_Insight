"use client";
import { useActionState, useState } from "react";
import { postTransactionAction } from "@/lib/actions/transactions";
import { Field, Input, Select } from "@/components/ui/form";
import { Alert, Button, Card } from "@/components/ui/primitives";
import { TRANSACTION_LABELS, transactionOperations, pairedOperation } from "@/lib/finance/transaction-operations";
import { CATEGORY_LABELS } from "@/lib/format";
import { TRANSACTION_CATEGORIES, type Account, type TransactionOperation } from "@/lib/types";

export function TransactionForm({account,others,requestId}: {account:Account;others:Account[];requestId:string}) {
  const operations = transactionOperations(account.type);
  const [operation,setOperation] = useState<TransactionOperation>(operations[0]);
  const [state,action,pending] = useActionState(postTransactionAction,{requestId});
  const paired = pairedOperation(operation);
  const showCategory = ["purchase","payment","refund"].includes(operation);
  if (!operations.length) return null;
  return <Card title="Simulate a transaction" description="Update fictional balances and history. No real money moves.">
    <form key={state.requestId} action={action} className="space-y-4">
      <input type="hidden" name="account_id" value={account.id}/>
      <input type="hidden" name="request_id" value={state.requestId}/>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="transaction-operation" label="Transaction type">{describedBy=><Select id="transaction-operation" name="operation" value={operation} onChange={event=>setOperation(event.target.value as TransactionOperation)} aria-describedby={describedBy}>{operations.map(value=><option key={value} value={value}>{TRANSACTION_LABELS[value]}</option>)}</Select>}</Field>
        <Field id="transaction-amount" label={`Amount (${account.currency})`} hint="Up to 1,000,000.00 per simulated transaction.">{describedBy=><Input id="transaction-amount" name="amount" type="number" min="0.01" max="1000000" step="0.01" required defaultValue={state.values?.amount ?? ""} aria-describedby={describedBy}/>}</Field>
      </div>
      {paired ? <Field id="transaction-counterparty" label={operation === "transfer" ? "Destination account" : "Pay from"} hint="Choose your checking or savings account at the same mock bank.">{describedBy=><Select id="transaction-counterparty" name="counterparty_account_id" required defaultValue={state.values?.counterparty_account_id ?? ""} aria-describedby={describedBy}><option value="" disabled>Select an account</option>{others.map(other=><option key={other.id} value={other.id}>{other.name} · {other.last4}</option>)}</Select>}</Field> : null}
      {showCategory ? <Field id="transaction-category" label="Category">{describedBy=><Select id="transaction-category" name="category" defaultValue={state.values?.category ?? (operation === "payment" ? "utilities" : "shopping")} aria-describedby={describedBy}>{TRANSACTION_CATEGORIES.filter(category=>!["salary","transfers","debt_payment"].includes(category)).map(category=><option key={category} value={category}>{CATEGORY_LABELS[category]}</option>)}</Select>}</Field> : null}
      <Field id="transaction-merchant" label={operation === "salary" ? "Employer (optional)" : "Merchant / payee (optional)"}>{describedBy=><Input id="transaction-merchant" name="merchant" defaultValue={state.values?.merchant ?? ""} maxLength={120} aria-describedby={describedBy}/>}</Field>
      <Field id="transaction-description" label="Description (optional)">{describedBy=><Input id="transaction-description" name="description" defaultValue={state.values?.description ?? ""} maxLength={200} aria-describedby={describedBy}/>}</Field>
      {operation === "loan_payment" ? <p className="text-xs text-muted">This is a principal-only payment on the mock bank's loan account. It does not change a separate lender application's projected schedule, interest, taxes, or escrow.</p> : null}
      {paired && !others.length ? <Alert tone="warn">This action needs a checking or savings account at the same mock bank.</Alert> : null}
      {state.error ? <Alert tone="bad" role="alert">{state.error}</Alert> : state.message ? <Alert tone="good" role="status">{state.message}</Alert> : null}
      <Button type="submit" disabled={pending || (paired && !others.length)}>{pending ? "Recording..." : "Record simulated transaction"}</Button>
    </form>
  </Card>;
}

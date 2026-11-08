import Form from "next/form";
import { Input, Select } from "@/components/ui/form";
import { Money } from "@/components/ui/money";
import { Badge, Button, ButtonLink } from "@/components/ui/primitives";
import { CATEGORY_LABELS, formatDate } from "@/lib/format";
import { TRANSACTION_CATEGORIES, type Transaction } from "@/lib/types";
import { TRANSACTION_LABELS } from "@/lib/finance/transaction-operations";
import type { TransactionOperation } from "@/lib/types";

const transactionLabel = (transaction: Transaction) => {
  if (transaction.category === "salary") return "Salary / paycheck";
  if (transaction.category === "debt_payment" && transaction.type === "payment") return "Debt payment";
  if (transaction.type === "transfer") return "Transfer";
  return TRANSACTION_LABELS[transaction.type as TransactionOperation] ?? transaction.type.replaceAll("_"," ");
};

/** Signed from the customer's cash perspective: credits +, debits -. */
const signedAmount = (transaction: Transaction) => (transaction.direction === "credit" ? transaction.amount : `-${transaction.amount}`);

export interface FilterValues {
  category?: string;
  start?: string;
  end?: string;
}

/**
 * A GET form: filters live in the URL, so results are shareable, the back
 * button works, and it functions before JavaScript loads. `next/form` adds
 * client-side navigation once it does.
 */
export function TransactionFilters({ accountId, values }: { accountId: string; values: FilterValues }) {
  const action = `/accounts/${encodeURIComponent(accountId)}`;
  const active = Boolean(values.category || values.start || values.end);
  return (
    <Form action={action} scroll={false} className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end">
      <div className="flex flex-col gap-1.5">
        <label htmlFor="filter-category" className="text-sm font-medium">
          Category
        </label>
        <Select id="filter-category" name="category" defaultValue={values.category ?? ""}>
          <option value="">All categories</option>
          {TRANSACTION_CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {CATEGORY_LABELS[category]}
            </option>
          ))}
        </Select>
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="filter-start" className="text-sm font-medium">
          From
        </label>
        <Input id="filter-start" name="start" type="date" defaultValue={values.start} />
      </div>
      <div className="flex flex-col gap-1.5">
        <label htmlFor="filter-end" className="text-sm font-medium">
          To
        </label>
        <Input id="filter-end" name="end" type="date" defaultValue={values.end} />
      </div>
      <div className="flex gap-2">
        <Button type="submit">Apply</Button>
        {active ? (
          <ButtonLink href={action} variant="secondary" scroll={false}>
            Clear
          </ButtonLink>
        ) : null}
      </div>
    </Form>
  );
}

export function TransactionList({ transactions, caption }: { transactions: Transaction[]; caption: string }) {
  return (
    <>
      {/* Phone: stacked rows */}
      <ul className="divide-y divide-border sm:hidden">
        {transactions.map((transaction) => (
          <li key={transaction.id} className="flex items-start justify-between gap-3 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{transaction.description}</p>
              <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted">
                {formatDate(transaction.date)} <Badge>{CATEGORY_LABELS[transaction.category]}</Badge><Badge>{transactionLabel(transaction)}</Badge>
              </p>
            </div>
            <Money value={signedAmount(transaction)} signed tone="flow" className="text-sm font-semibold" />
          </li>
        ))}
      </ul>
      {/* Tablet and up: a real table with headers */}
      <div className="hidden overflow-x-auto sm:block">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr className="border-b border-border text-xs text-muted">
              <th scope="col" className="py-2 pr-4 font-medium">Date</th>
              <th scope="col" className="py-2 pr-4 font-medium">Description</th>
              <th scope="col" className="py-2 pr-4 font-medium">Category</th>
              <th scope="col" className="py-2 pr-4 font-medium">Type</th>
              <th scope="col" className="py-2 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((transaction) => (
              <tr key={transaction.id} className="border-b border-border last:border-0">
                <td className="py-2.5 pr-4 whitespace-nowrap tabular-nums text-muted">{formatDate(transaction.date)}</td>
                <td className="py-2.5 pr-4">
                  <span className="font-medium">{transaction.description}</span>
                </td>
                <td className="py-2.5 pr-4">
                  <Badge>{CATEGORY_LABELS[transaction.category]}</Badge>
                </td>
                <td className="py-2.5 pr-4 text-muted"><span>{transactionLabel(transaction)}</span><span className="block text-xs capitalize">{transaction.direction}</span></td>
                <td className="py-2.5 text-right font-semibold">
                  <Money value={signedAmount(transaction)} signed tone="flow" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

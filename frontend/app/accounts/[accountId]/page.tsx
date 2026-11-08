import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { randomUUID } from "node:crypto";
import { TransactionForm } from "@/components/accounts/transaction-form";
import { dataSourceKind } from "@/lib/data";
import { utilizationOf } from "@/components/accounts/account-card";
import { TransactionFilters, TransactionList, type FilterValues } from "@/components/accounts/transactions";
import { Money } from "@/components/ui/money";
import { Pagination } from "@/components/ui/pagination";
import { Alert, Badge, ButtonLink, Card, DetailList, EmptyState, LoadingBlock, Meter, Skeleton, TextLink } from "@/components/ui/primitives";
import { getDataProvider } from "@/lib/data";
import { ACCOUNT_TYPE_LABELS, CATEGORY_LABELS, formatDate, formatInteger, formatMoney, formatRate, formatRatio, formatTerm } from "@/lib/format";
import { firstParam, isIsoDate, parsePage, type SearchParams } from "@/lib/search-params";
import { TRANSACTION_CATEGORIES, type Account, type TransactionCategory } from "@/lib/types";

export const metadata: Metadata = { title: "Account details" };

const PAGE_SIZE = 10;

function AccountSummary({ account }: { account: Account }) {
  const { details } = account;
  const owed = account.classification === "liability";
  const utilization = utilizationOf(account);
  return (
    <Card>
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <div className="lg:w-64 lg:shrink-0">
          <p className="text-sm text-muted">{owed ? "Amount owed" : "Current balance"}</p>
          <Money value={account.balance} className="text-3xl font-semibold tracking-tight" />
          <p className="mt-1 text-xs text-muted">As of {formatDate(account.updatedAt)}</p>
          {utilization !== null ? (
            <div className="mt-4 space-y-1.5">
              <p className="text-xs text-muted">{formatRatio(utilization, { whole: true })} of credit limit used</p>
              <Meter value={utilization} label="Credit used" tone={utilization > 0.3 ? "warn" : "info"} />
            </div>
          ) : null}
        </div>
        <div className="min-w-0 flex-1">
          <DetailList
            items={[
              { label: "Account type", value: ACCOUNT_TYPE_LABELS[account.type] },
              { label: "Account number", value: `•••• ${account.last4}` },
              details.apy ? { label: "APY", value: formatRate(details.apy) } : null,
              details.creditLimit ? { label: "Credit limit", value: formatMoney(details.creditLimit) } : null,
              details.purchaseApr ? { label: "Purchase APR", value: formatRate(details.purchaseApr) } : null,
              details.minimumPayment ? { label: "Minimum payment", value: formatMoney(details.minimumPayment) } : null,
              details.paymentDueDate ? { label: "Payment due", value: formatDate(details.paymentDueDate) } : null,
              details.originalPrincipal ? { label: "Original principal", value: formatMoney(details.originalPrincipal) } : null,
              details.outstandingPrincipal ? { label: "Outstanding principal", value: formatMoney(details.outstandingPrincipal) } : null,
              details.apr ? { label: "APR", value: formatRate(details.apr) } : null,
              details.monthlyPayment ? { label: "Monthly payment", value: formatMoney(details.monthlyPayment) } : null,
              details.termMonths ? { label: "Term", value: formatTerm(details.termMonths) } : null,
              details.maturityDate ? { label: "Matures", value: formatDate(details.maturityDate) } : null,
              details.accountValue ? { label: "Account value", value: formatMoney(details.accountValue) } : null,
              details.subtype ? { label: "Subtype", value: details.subtype[0].toUpperCase() + details.subtype.slice(1) } : null,
              { label: "Opening balance", value: account.openingBalance === null ? "Not provided by institution" : `${formatMoney(account.openingBalance)} on ${formatDate(account.createdAt)}` },
            ]}
          />
        </div>
      </div>
      <p className="mt-5 border-t border-border pt-3 font-mono text-[11px] text-muted break-all">
        Source: {account.source.service} · {account.source.institutionId} · {account.source.recordId}
      </p>
    </Card>
  );
}

function parseFilters(params: SearchParams) {
  const errors: string[] = [];
  const values: FilterValues = { category: firstParam(params, "category"), start: firstParam(params, "start"), end: firstParam(params, "end") };
  let category: TransactionCategory | undefined;
  if (values.category) {
    if ((TRANSACTION_CATEGORIES as readonly string[]).includes(values.category)) category = values.category as TransactionCategory;
    else errors.push(`“${values.category}” is not a supported category.`);
  }
  if (values.start && !isIsoDate(values.start)) errors.push("The start date must be a valid date (YYYY-MM-DD).");
  if (values.end && !isIsoDate(values.end)) errors.push("The end date must be a valid date (YYYY-MM-DD).");
  if (!errors.length && values.start && values.end && values.start > values.end) errors.push("The start date must be on or before the end date.");
  return { values, errors, category, page: parsePage(params) };
}

async function AccountDetail({ params, searchParams }: { params: Promise<{ accountId: string }>; searchParams: Promise<SearchParams> }) {
  const [{ accountId }, query] = await Promise.all([params, searchParams]);
  const provider = getDataProvider();
  const account = await provider.getAccount(accountId);
  // Missing and not-owned accounts look the same, as with the service's 404.
  if (!account) notFound();
  const canPost = dataSourceKind() === "http" && account.source.service === "mock_bank";
  const fundingAccounts = canPost ? (await provider.listAccounts()).filter(other=>other.id!==account.id && other.institution.id===account.institution.id && other.currency===account.currency && ["checking","savings"].includes(other.type)) : [];

  const filters = parseFilters(query);
  const page = filters.errors.length
    ? null
    : await provider.listTransactions(account.id, {
        limit: PAGE_SIZE,
        offset: (filters.page - 1) * PAGE_SIZE,
        category: filters.category,
        startDate: filters.values.start,
        endDate: filters.values.end,
      });
  const pageCount = page ? Math.ceil(page.total / PAGE_SIZE) : 0;
  const filtered = Boolean(filters.values.category || filters.values.start || filters.values.end);
  const owed = account.classification === "liability";

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm text-muted">{account.institution.name}</p>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{account.name}</h1>
        </div>
        <div className="flex gap-2">
          <Badge tone={owed ? "warn" : "info"}>{owed ? "Liability" : "Asset"}</Badge>
          <Badge tone="demo">◆ Demo data</Badge>
        </div>
      </header>

      <AccountSummary account={account} />
      {canPost ? <TransactionForm account={account} others={fundingAccounts} requestId={randomUUID()}/> : null}

      <Card
        title="Transactions"
        description={
          owed
            ? "On this account, debits (purchases) increase what you owe and credits (payments) reduce it."
            : "Credits add to this balance and debits subtract from it."
        }
      >
        <div className="space-y-4">
          <TransactionFilters accountId={account.id} values={filters.values} />
          {filters.errors.length ? (
            <Alert tone="bad" role="alert" title="Check your filters">
              <ul className="list-disc pl-4">
                {filters.errors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </Alert>
          ) : page && page.total === 0 ? (
            <EmptyState
              title={filtered ? "No transactions match these filters" : "No transactions in this period"}
              description={
                filtered
                  ? "Try a wider date range or a different category."
                  : `This ${ACCOUNT_TYPE_LABELS[account.type].toLowerCase()} has no activity in the history the institution shares.`
              }
              action={filtered ? <ButtonLink href={`/accounts/${encodeURIComponent(account.id)}`} variant="secondary">Clear filters</ButtonLink> : undefined}
            />
          ) : page && page.items.length === 0 ? (
            <EmptyState title="This page is past the end of the list" action={<TextLink href={`/accounts/${encodeURIComponent(account.id)}`}>Go to the first page</TextLink>} />
          ) : page ? (
            <>
              <p className="text-sm text-muted" aria-live="polite">
                Showing {formatInteger(page.offset + 1)}–{formatInteger(page.offset + page.items.length)} of {formatInteger(page.total)}
                {filters.category ? ` ${CATEGORY_LABELS[filters.category].toLowerCase()}` : ""} transactions, newest first
              </p>
              <TransactionList transactions={page.items} caption={`Transactions for ${account.name}`} />
              <Pagination
                label="Transaction pages"
                path={`/accounts/${encodeURIComponent(account.id)}`}
                params={{ category: filters.values.category, start: filters.values.start, end: filters.values.end }}
                page={filters.page}
                pageCount={pageCount}
              />
            </>
          ) : null}
        </div>
      </Card>
    </div>
  );
}

function AccountDetailSkeleton() {
  return (
    <LoadingBlock label="Loading account">
      <div className="space-y-6">
        <Skeleton className="h-12 w-72 max-w-full" />
        <Skeleton className="h-56" />
        <Skeleton className="h-96" />
      </div>
    </LoadingBlock>
  );
}

export default function AccountDetailPage({ params, searchParams }: PageProps<"/accounts/[accountId]">) {
  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-4 text-sm">
        <TextLink href="/accounts">
          <span aria-hidden="true">← </span>All accounts
        </TextLink>
      </nav>
      <Suspense fallback={<AccountDetailSkeleton />}>
        <AccountDetail params={params} searchParams={searchParams} />
      </Suspense>
    </>
  );
}

import Link from "next/link";
import { ColumnChart, RankedBars } from "@/components/charts/bars";
import { Money } from "@/components/ui/money";
import { Badge, ButtonLink, Card, EmptyState, LoadingBlock, Skeleton, StatTile, TextLink } from "@/components/ui/primitives";
import { getDataProvider } from "@/lib/data";
import { toCents } from "@/lib/finance/money";
import { ACCOUNT_TYPE_LABELS, CATEGORY_LABELS, formatDate, formatMonth, formatMoney, formatShortDate } from "@/lib/format";
import type { BreakdownItem, Dashboard } from "@/lib/types";

function recordHref(item: BreakdownItem): string {
  if (item.source.service === "mock_loan") return `/loans/${encodeURIComponent(item.id)}`;
  if (item.source.service === "mock_mortgage") return `/mortgages/${encodeURIComponent(item.id)}`;
  return `/accounts/${encodeURIComponent(item.id)}`;
}

function BreakdownList({ items, emptyLabel }: { items: BreakdownItem[]; emptyLabel: string }) {
  if (items.length === 0) return <p className="text-sm text-muted">{emptyLabel}</p>;
  return (
    <ul className="divide-y divide-border">
      {items.map((item) => (
        <li key={item.id} className="flex items-center justify-between gap-3 py-2.5">
          <div className="min-w-0">
            <Link href={recordHref(item)} className="block truncate text-sm font-medium hover:underline">
              {item.label}
            </Link>
            <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
              {item.institutionName} · {ACCOUNT_TYPE_LABELS[item.type]}
              {item.basisNote ? <Badge tone="demo">{item.basisNote}</Badge> : null}
            </p>
          </div>
          <Money value={item.amount} className="text-sm font-medium" />
        </li>
      ))}
    </ul>
  );
}

function Obligations({ dashboard }: { dashboard: Dashboard }) {
  if (dashboard.obligations.length === 0) {
    return <EmptyState title="Nothing due soon" description="No payments are scheduled in the 45 days after the snapshot." />;
  }
  return (
    <ul className="divide-y divide-border">
      {dashboard.obligations.map((obligation) => (
        <li key={obligation.id} className="flex items-start gap-3 py-3">
          <div className="w-14 shrink-0 rounded-lg bg-surface-muted py-1.5 text-center text-xs font-semibold" aria-hidden={obligation.dueDate ? undefined : true}>
            {obligation.dueDate ? formatShortDate(obligation.dueDate) : "—"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">{obligation.label}</p>
            <p className="text-xs text-muted">
              {obligation.institutionName}
              {obligation.dueDate ? ` · Due ${formatDate(obligation.dueDate)}` : ""}
              {obligation.note && !obligation.note.startsWith("Statement") ? ` · ${obligation.note}` : ""}
            </p>
          </div>
          <div className="text-right">
            <Money value={obligation.amount} className="text-sm font-semibold" />
            <p className="text-xs text-muted">{obligation.amountLabel}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

export async function DashboardContent() {
  const dashboard = await getDataProvider().getDashboard();

  if (dashboard.connectedInstitutions.length === 0) {
    return (
      <EmptyState
        title="No institutions connected"
        description="Connect a mock bank or lender to see balances, spending and upcoming payments."
        action={<ButtonLink href="/connect">Connect an institution</ButtonLink>}
      />
    );
  }

  const negativeNetWorth = toCents(dashboard.totals.netWorth) < 0n;
  const hasMortgage = dashboard.liabilities.some((item) => item.type === "mortgage");
  const months = dashboard.cashFlow;

  return (
    <div className="space-y-6">
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Net worth"
          value={formatMoney(dashboard.totals.netWorth)}
          tone={negativeNetWorth ? "bad" : "neutral"}
          hint={hasMortgage ? "Assets minus liabilities. Home value is not an account, so it is not included." : "Assets minus liabilities."}
        />
        <StatTile label="Assets" value={formatMoney(dashboard.totals.assets)} hint={`${dashboard.assets.length} accounts`} />
        <StatTile label="Liabilities" value={formatMoney(dashboard.totals.liabilities)} hint={`${dashboard.liabilities.length} cards and loans`} />
        <StatTile
          label="Spending, last 30 days"
          value={formatMoney(dashboard.spending.total)}
          hint={`${formatShortDate(dashboard.spending.windowStart)} – ${formatDate(dashboard.spending.windowEnd)}`}
        />
      </dl>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Monthly cash flow" description="Paychecks compared with spending. Transfers and debt payments are excluded.">
          {months.length > 0 ? (
            <ColumnChart
              mode="grouped"
              caption="Monthly income and spending"
              seriesA="Income"
              seriesB="Spending"
              data={months.map((month) => ({
                key: month.month,
                label: formatMonth(month.month),
                a: month.income,
                b: month.spending,
                note: month.partial ? "Partial month in demo data" : undefined,
              }))}
            />
          ) : (
            <EmptyState title="No transactions yet" description="Connect a bank to see cash flow." />
          )}
        </Card>

        <Card title="Spending by category" description={`Last 30 days, across checking, savings and cards.`}>
          {dashboard.spending.byCategory.length > 0 ? (
            <RankedBars
              caption="Spending by category, last 30 days"
              total={dashboard.spending.total}
              items={dashboard.spending.byCategory.map((entry) => ({
                key: entry.category,
                label: CATEGORY_LABELS[entry.category],
                value: entry.amount,
                detail: `${entry.count} ${entry.count === 1 ? "transaction" : "transactions"}`,
              }))}
            />
          ) : (
            <EmptyState title="No spending in this period" />
          )}
          <p className="mt-3 text-xs text-muted">
            Card payments, transfers between your accounts and paychecks are not counted, so nothing is counted twice.
          </p>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <Card
          className="xl:col-span-3"
          title="Upcoming payments"
          description={`Due in the 45 days after ${formatDate(dashboard.snapshotDate)}.`}
        >
          <Obligations dashboard={dashboard} />
        </Card>
        <Card
          className="xl:col-span-2"
          title="Connections"
          action={<TextLink href="/connect" className="text-sm">Manage</TextLink>}
        >
          <ul className="flex flex-wrap gap-2">
            {dashboard.connectedInstitutions.map((institution) => (
              <li key={institution.id}>
                <Badge tone="good">
                  <span aria-hidden="true">●</span> {institution.name}
                </Badge>
              </li>
            ))}
          </ul>
          {dashboard.availableInstitutions.length > 0 ? (
            <p className="mt-4 text-sm text-muted">
              Not connected: {dashboard.availableInstitutions.map((institution) => institution.name).join(", ")}.{" "}
              <TextLink href="/connect">Connect</TextLink>
            </p>
          ) : null}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card title="Assets" action={<Money value={dashboard.totals.assets} className="text-sm font-semibold" />}>
          <BreakdownList items={dashboard.assets} emptyLabel="No asset accounts connected." />
        </Card>
        <Card title="Liabilities" action={<Money value={dashboard.totals.liabilities} className="text-sm font-semibold" />}>
          <BreakdownList items={dashboard.liabilities} emptyLabel="No cards or loans connected." />
          {dashboard.liabilities.some((item) => item.basisNote) ? (
            <p className="mt-3 text-xs text-muted">
              Lender balances are a demo servicing snapshot: the lender APIs report only the original amount and a projected schedule.
            </p>
          ) : null}
        </Card>
      </div>
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <LoadingBlock label="Loading your overview">
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((key) => (
            <Skeleton key={key} className="h-28" />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
        <Skeleton className="h-64" />
      </div>
    </LoadingBlock>
  );
}

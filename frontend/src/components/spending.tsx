import type { SWRResponse } from "swr";

import type { ApiError, Schemas } from "@/lib/api";
import { categoryLabel, formatDate, formatMoney, formatMoneyWhole } from "@/lib/format";

import { Empty, ErrorNotice, Skeleton } from "./states";

type Props = { flow: SWRResponse<Schemas["CashFlowSummary"], ApiError> };

/**
 * One series (spending by category), so one color, sorted biggest first, with each
 * bar's value written next to it. Bar widths are a visual encoding only; every
 * number shown comes from the backend.
 */
export function Spending({ flow }: Props) {
  return (
    <section aria-labelledby="spending-heading">
      <h2 id="spending-heading" className="text-xl font-semibold">
        Where your money goes
      </h2>
      <div className="mt-4">
        {flow.error ? (
          <ErrorNotice error={flow.error} onRetry={() => void flow.mutate()} />
        ) : !flow.data ? (
          <Skeleton lines={5} />
        ) : (
          <SpendingBody summary={flow.data} />
        )}
      </div>
    </section>
  );
}

function SpendingBody({ summary }: { summary: Schemas["CashFlowSummary"] }) {
  const { by_category, monthly_income, monthly_spending, start, end, months } = summary;
  const largest = Math.max(...by_category.map((c) => Number(c.monthly_average)), 1);

  return (
    <>
      <dl className="grid grid-cols-2 gap-4 border-y border-line py-4">
        <div>
          <dt className="text-sm text-ink-3">Comes in each month</dt>
          <dd className="mt-1 text-2xl font-semibold">{formatMoneyWhole(monthly_income)}</dd>
        </div>
        <div>
          <dt className="text-sm text-ink-3">Goes out each month</dt>
          <dd className="mt-1 text-2xl font-semibold">{formatMoneyWhole(monthly_spending)}</dd>
        </div>
      </dl>

      {by_category.length === 0 ? (
        <div className="py-6">
          <Empty>No spending in this period yet.</Empty>
        </div>
      ) : (
        <ul className="mt-5 space-y-3" aria-label="Monthly spending by category">
          {by_category.map((c) => (
            <li
              key={c.category}
              className="grid grid-cols-[7.5rem_1fr_auto] items-center gap-3"
              title={`${categoryLabel(c.category)}: ${formatMoney(c.monthly_average)} a month`}
            >
              <span className="truncate text-sm">{categoryLabel(c.category)}</span>
              <span className="h-3" aria-hidden="true">
                <span
                  className="block h-full rounded-r bg-accent"
                  style={{ width: `${Math.max((Number(c.monthly_average) / largest) * 100, 1)}%` }}
                />
              </span>
              <span className="text-right text-sm font-medium">{formatMoney(c.monthly_average)}</span>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-5 text-sm text-ink-3">
        Monthly average over {months} {months === 1 ? "month" : "months"}, {formatDate(start)} to{" "}
        {formatDate(end)}. Card payments between your own accounts aren&apos;t counted twice.
      </p>
    </>
  );
}

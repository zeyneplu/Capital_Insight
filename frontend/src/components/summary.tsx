import type { SWRResponse } from "swr";

import type { ApiError, Schemas } from "@/lib/api";
import { rankInsights } from "@/lib/insights";

import { ErrorNotice, Skeleton } from "./states";

type Props = {
  profile: SWRResponse<Schemas["FinancialProfile"], ApiError>;
  report: SWRResponse<Schemas["HealthReport"], ApiError>;
};

/** The top of the dashboard: the single most important thing, in one sentence. */
export function Summary({ profile, report }: Props) {
  const error = profile.error ?? report.error;
  if (error) {
    return (
      <ErrorNotice
        error={error}
        onRetry={() => {
          void profile.mutate();
          void report.mutate();
        }}
      />
    );
  }
  if (!profile.data || !report.data) return <Skeleton lines={3} className="max-w-2xl" />;

  const { display_name, accounts } = profile.data;
  const banks = new Set(accounts.map((a) => a.institution)).size;
  const top = rankInsights(report.data)[0];

  return (
    <section aria-labelledby="summary-heading" className="max-w-3xl">
      <p className="text-ink-2">
        {display_name} has {accounts.length} {accounts.length === 1 ? "account" : "accounts"} at{" "}
        {banks} {banks === 1 ? "bank" : "banks"}.
      </p>
      <h1
        id="summary-heading"
        className="mt-3 text-4xl font-semibold leading-[1.1] tracking-tight text-balance sm:text-5xl"
      >
        {top ? top.headline : "Connect a bank to see where you stand."}
      </h1>
      {top?.advice && <p className="mt-4 max-w-[60ch] text-lg text-ink-2">{top.advice}</p>}
    </section>
  );
}

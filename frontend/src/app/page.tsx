"use client";

/**
 * Dashboard. Data loads in the browser (open DevTools → Network to watch each request
 * go to the backend and come back as JSON). Each section shows its own loading and
 * error state, so one slow request never blanks the whole page.
 */
import { Accounts } from "@/components/accounts";
import { HealthList } from "@/components/health-list";
import { Spending } from "@/components/spending";
import { ErrorNotice } from "@/components/states";
import { Summary } from "@/components/summary";
import { DEMO_CUSTOMER } from "@/lib/config";
import { useCashFlow, useHealthReport, useProfile } from "@/lib/queries";

export default function DashboardPage() {
  const profile = useProfile(DEMO_CUSTOMER);
  const report = useHealthReport(DEMO_CUSTOMER);
  const flow = useCashFlow(DEMO_CUSTOMER);

  // If the API itself is unreachable, say so once instead of in every section.
  const queries = [profile, report, flow];
  const unreachable = queries.every((q) => q.error?.status === 0) ? profile.error : undefined;

  return (
    <>
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <span className="font-semibold tracking-tight">Capital Insight</span>
          <span className="text-sm text-ink-3">Demo data</span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-14">
        {unreachable ? (
          <ErrorNotice
            error={unreachable}
            onRetry={() => queries.forEach((q) => void q.mutate())}
          />
        ) : (
          <>
            <Summary profile={profile} report={report} />

            <div className="mt-14 grid gap-x-16 gap-y-12 lg:grid-cols-2">
              <HealthList report={report} />
              <Spending flow={flow} />
            </div>

            <div className="mt-14">
              <Accounts profile={profile} />
            </div>
          </>
        )}
      </main>

      <footer className="mx-auto max-w-6xl px-5 pb-10 text-sm text-ink-3 sm:px-8">
        Synthetic demo data. Capital Insight offers education, not financial advice.
      </footer>
    </>
  );
}

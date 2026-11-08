import Link from "next/link";
import { ForecastChart } from "@/components/planning/forecast-chart";
import { GOAL_TEMPLATES } from "@/lib/planning-goals";
import { dataSourceKind } from "@/lib/data";
import { Alert, Card, TextLink } from "@/components/ui/primitives";
import { formatMoney } from "@/lib/format";
import { loadPlanningOverview } from "@/lib/planning-server";

/**
 * Optional Overview additions. Only goals marked "show on dashboard" and features
 * the user switched on in Plan & goals → Customize are rendered.
 */
export async function PlanningWidgets() {
  // Fixture dashboards never mix in live account data.
  if (dataSourceKind() !== "http") return null;
  const result = await loadPlanningOverview();
  if (result.status === "unconfigured" || result.status === "signed-out") return null;
  if (result.status === "error") return <Alert tone="warn">Your goals could not be loaded right now. Balances below are unaffected.</Alert>;

  const { preferences: prefs, goals, snapshot, forecast } = result.data;
  const pinned = goals.filter((goal) => goal.show_on_dashboard);
  const anything = pinned.length || prefs.show_forecast || prefs.show_subscriptions || prefs.show_spending;

  return (
    <div className="space-y-6">
      <Link
        href="/sam"
        className="group flex items-center gap-4 rounded-2xl border border-sky-400/20 bg-gradient-to-r from-slate-950 via-blue-950 to-indigo-950 p-4 text-white transition hover:border-sky-300/50 sm:p-5"
      >
        <span aria-hidden="true" className="grid size-11 shrink-0 place-items-center rounded-full bg-gradient-to-br from-sky-400 via-indigo-500 to-violet-500 font-bold">
          S
        </span>
        <span className="min-w-0 flex-1">
          <strong className="block">Questions about your money? Ask Sam.</strong>
          <span className="text-sm text-blue-200">
            {snapshot.alerts.length
              ? `${snapshot.alerts.length} spending check-in${snapshot.alerts.length === 1 ? "" : "s"} to review`
              : snapshot.subscriptions.length
                ? `${snapshot.subscriptions.length} possible subscriptions detected. Make sure you need them.`
                : "Budgets, credit habits, savings goals and big purchases."}
          </span>
        </span>
        <span aria-hidden="true" className="text-sky-300 transition group-hover:translate-x-1">→</span>
      </Link>

      {!anything ? (
        <Card title="Make Overview yours">
          <p className="text-sm text-muted">
            Add a goal for education, a car or retirement, or switch on forecasts and spending check-ins. They’ll appear here.
          </p>
          <TextLink href="/planning" className="mt-3 inline-block text-sm font-semibold">Set up a goal →</TextLink>
        </Card>
      ) : null}

      {pinned.length ? (
        <section aria-labelledby="dash-goals">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="dash-goals" className="text-base font-semibold">Your goals</h2>
            <TextLink href="/planning" className="text-sm">Manage</TextLink>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {pinned.slice(0, 6).map((goal) => {
              const color = GOAL_TEMPLATES.find((item) => item.kind === goal.kind)?.color ?? "#38bdf8";
              const progress = Math.round(goal.projection?.progress_pct ?? 0);
              return (
                <li key={goal.id} className="rounded-xl border border-border bg-surface p-4" style={{ borderTop: `4px solid ${color}` }}>
                  <p className="truncate font-semibold">{goal.name}</p>
                  {goal.kind === "credit" ? (
                    <>
                      <p className="mt-2 text-2xl font-semibold tabular-nums">
                        {snapshot.credit_score?.score ?? "—"} <span className="text-muted">→</span> <span style={{ color }}>{goal.target_score}</span>
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        {goal.target_utilization_pct}% utilization target · {goal.months} months
                        {goal.projection?.cards?.length ? ` · ${formatMoney(goal.projection.monthly_payment ?? "0")}/mo` : ""}
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="mt-1 text-xs text-muted">
                        {formatMoney(goal.saved_amount)} of {formatMoney(goal.target_amount)}
                      </p>
                      <div
                        role="progressbar"
                        aria-label={`${goal.name} progress`}
                        aria-valuenow={progress}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        className="mt-3 h-2.5 overflow-hidden rounded-full bg-surface-muted"
                      >
                        <div className="h-full rounded-full" style={{ width: `${progress}%`, background: color }} />
                      </div>
                      <p className="mt-2 text-xs text-muted">
                        {goal.projection?.on_track ? "On track in this scenario" : `Needs ${formatMoney(goal.projection?.required_monthly ?? "0")}/mo`} · {goal.months} months
                      </p>
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {prefs.show_forecast || prefs.show_subscriptions || prefs.show_spending ? (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          {prefs.show_forecast ? (
            <Card title="Cash-flow forecast" description="A calculation from your history and goal allocations, not a guarantee.">
              {forecast.available ? (
                <ForecastChart points={forecast.points.map((point) => ({ month: point.month, amount: point.unallocated }))} label="Unallocated cash" color="#34d399" />
              ) : (
                <p className="text-sm text-muted">{forecast.reason}</p>
              )}
            </Card>
          ) : null}
          {prefs.show_subscriptions ? (
            <Card title="Subscriptions detected" description="Repeated, similarly priced charges. Make sure you still need them.">
              {snapshot.subscriptions.length ? (
                <ul className="divide-y divide-border">
                  {snapshot.subscriptions.slice(0, 5).map((item, index) => (
                    <li key={index} className="flex justify-between gap-3 py-2.5 text-sm">
                      <span>
                        <strong>{item.merchant}</strong>
                        <span className="block text-xs text-muted">{item.cadence}</span>
                      </span>
                      <strong className="tabular-nums">{formatMoney(item.monthly_estimate)}/mo</strong>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted">No recurring pattern found in the available history.</p>
              )}
            </Card>
          ) : null}
          {prefs.show_spending ? (
            <Card title="Spending check-in">
              {snapshot.alerts.length ? (
                <ul className="space-y-2">
                  {snapshot.alerts.map((alert) => (
                    <li key={alert.kind} className="rounded-lg bg-warn-soft p-3">
                      <strong className="text-sm text-warn">{alert.title}</strong>
                      <p className="text-lg font-semibold tabular-nums">{formatMoney(alert.amount)}</p>
                      <p className="text-xs text-muted">{alert.detail}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted">No overspending detected in the available data.</p>
              )}
            </Card>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

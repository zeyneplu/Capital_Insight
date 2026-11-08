import type { SWRResponse } from "swr";

import type { ApiError, Schemas } from "@/lib/api";
import { formatIndicator } from "@/lib/format";

import { ErrorNotice, Skeleton } from "./states";
import { StatusMark } from "./status-mark";

export function HealthList({ report }: { report: SWRResponse<Schemas["HealthReport"], ApiError> }) {
  return (
    <section aria-labelledby="health-heading">
      <h2 id="health-heading" className="text-xl font-semibold">
        Financial health
      </h2>
      <div className="mt-4">
        {report.error ? (
          <ErrorNotice error={report.error} onRetry={() => void report.mutate()} />
        ) : !report.data ? (
          <Skeleton lines={4} />
        ) : (
          <ul className="divide-y divide-line border-y border-line">
            {report.data.indicators.map((ind) => (
              <li key={ind.key} className="grid grid-cols-[1fr_auto] gap-x-6 gap-y-1 py-4">
                <p className="font-medium">{ind.label}</p>
                <p className="text-right font-semibold">{formatIndicator(ind)}</p>
                <p className="max-w-[52ch] text-sm text-ink-3">{ind.detail}</p>
                <p className="text-right">
                  <StatusMark status={ind.status} />
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

/**
 * Small, dependency-free bar charts rendered on the server.
 *
 * Money values arrive as decimal strings. Bar geometry is display-only, so it
 * converts to numbers at the last moment; labels always use exact strings.
 * Every mark has a hover AND keyboard-focus tooltip (CSS only), a legend
 * names each series, and each chart offers a table view.
 */
import type { ReactNode } from "react";
import { toCents } from "@/lib/finance/money";
import { formatMoney } from "@/lib/format";
import { cx } from "@/components/ui/primitives";

const dollars = (value: string) => Number(toCents(value)) / 100;

/** Rounds a maximum up to a readable axis value: 1, 2, 2.5 or 5 x 10^n. */
function niceMax(value: number): number {
  if (value <= 0) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 2.5, 5, 10]) {
    if (value <= step * magnitude) return step * magnitude;
  }
  return 10 * magnitude;
}

function Tooltip({ children, align = "center" }: { children: ReactNode; align?: "center" | "start" }) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        "pointer-events-none absolute bottom-full z-10 mb-2 w-max max-w-56 rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs text-text opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100",
        align === "center" ? "left-1/2 -translate-x-1/2" : "left-0",
      )}
    >
      {children}
    </span>
  );
}

export function Legend({ items }: { items: Array<{ label: string; colorClass: string }> }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-label="Legend">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <span aria-hidden="true" className={cx("inline-block size-2.5 rounded-sm", item.colorClass)} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

function TableView({ caption, headers, rows }: { caption: string; headers: string[]; rows: ReactNode[][] }) {
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-xs font-medium text-primary">Show data table</summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr className="border-b border-border text-muted">
              {headers.map((header, index) => (
                <th key={header} scope="col" className={cx("py-1.5 pr-3 font-medium", index > 0 && "text-right")}>
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b border-border last:border-0">
                {row.map((cell, index) =>
                  index === 0 ? (
                    <th key={index} scope="row" className="py-1.5 pr-3 font-normal">
                      {cell}
                    </th>
                  ) : (
                    <td key={index} className="py-1.5 pr-3 text-right tabular-nums">
                      {cell}
                    </td>
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

// ---------------------------------------------------------------------------
// Ranked horizontal bars: one series, one color (magnitude by length only).
// ---------------------------------------------------------------------------

export function RankedBars({
  items,
  caption,
  total,
}: {
  items: Array<{ key: string; label: string; value: string; detail?: string }>;
  caption: string;
  /** Used for "share of total" in tooltips. */
  total: string;
}) {
  const max = Math.max(...items.map((item) => dollars(item.value)), 0);
  const totalValue = dollars(total);
  return (
    <figure>
      <figcaption className="sr-only">{caption}</figcaption>
      <ul className="space-y-2.5">
        {items.map((item) => {
          const value = dollars(item.value);
          const share = totalValue > 0 ? Math.round((value / totalValue) * 100) : 0;
          return (
            <li key={item.key}>
              <div
                tabIndex={0}
                aria-label={`${item.label}: ${formatMoney(item.value)}, ${share}% of total${item.detail ? `, ${item.detail}` : ""}`}
                className="group relative grid grid-cols-[minmax(6.5rem,8rem)_1fr_auto] items-center gap-3 text-sm"
              >
                <span className="truncate text-muted">{item.label}</span>
                <span className="h-2.5 rounded-r-[4px] bg-series-1" style={{ width: `${max > 0 ? Math.max((value / max) * 100, 1.5) : 0}%` }} />
                <span className="tabular-nums font-medium">{formatMoney(item.value)}</span>
                <Tooltip>
                  <span className="font-semibold">{item.label}</span>
                  <br />
                  {formatMoney(item.value)} · {share}% of total
                  {item.detail ? (
                    <>
                      <br />
                      {item.detail}
                    </>
                  ) : null}
                </Tooltip>
              </div>
            </li>
          );
        })}
      </ul>
      <TableView caption={caption} headers={["Category", "Amount", "Share"]} rows={items.map((item) => [item.label, formatMoney(item.value), `${totalValue > 0 ? Math.round((dollars(item.value) / totalValue) * 100) : 0}%`])} />
    </figure>
  );
}

// ---------------------------------------------------------------------------
// Vertical bars with two series, grouped or stacked, on one shared axis.
// ---------------------------------------------------------------------------

interface ColumnDatum {
  key: string;
  label: string;
  /** Shorter label for narrow axes; falls back to `label`. */
  axisLabel?: string;
  a: string;
  b: string;
  note?: string;
}

export function ColumnChart({
  data,
  caption,
  seriesA,
  seriesB,
  mode,
  height = 180,
  labelEvery = 1,
}: {
  data: ColumnDatum[];
  caption: string;
  seriesA: string;
  seriesB: string;
  mode: "grouped" | "stacked";
  height?: number;
  /** Show every Nth axis label (dense charts). */
  labelEvery?: number;
}) {
  const peak = Math.max(...data.map((d) => (mode === "stacked" ? dollars(d.a) + dollars(d.b) : Math.max(dollars(d.a), dollars(d.b)))), 0);
  const axisMax = niceMax(peak);
  const ticks = [0, axisMax / 2, axisMax];
  const pct = (value: string) => (dollars(value) / axisMax) * 100;

  return (
    <figure>
      <figcaption className="sr-only">{caption}</figcaption>
      <Legend
        items={[
          { label: seriesA, colorClass: "bg-series-1" },
          { label: seriesB, colorClass: "bg-series-2" },
        ]}
      />
      {/* mt-6 leaves room for the top tick label, which is centered on the top gridline. */}
      <div className="mt-6 flex gap-2">
        {/* y-axis labels */}
        <div className="relative w-12 shrink-0 text-right text-[11px] text-muted" style={{ height }} aria-hidden="true">
          {ticks.map((tick) => (
            <span key={tick} className="absolute right-0 -translate-y-1/2 tabular-nums" style={{ bottom: `${(tick / axisMax) * 100}%` }}>
              {formatMoney(String(tick), { whole: true })}
            </span>
          ))}
        </div>
        <div className="min-w-0 flex-1">
          <div className="relative" style={{ height }}>
            {ticks.map((tick) => (
              <span key={tick} aria-hidden="true" className="absolute inset-x-0 h-px bg-grid" style={{ bottom: `${(tick / axisMax) * 100}%` }} />
            ))}
            <ul className={cx("absolute inset-0 flex items-end", data.length > 12 ? "gap-[2px]" : "gap-3 sm:gap-6")}>
              {data.map((d) => (
                <li key={d.key} className="flex h-full min-w-0 flex-1 items-end justify-center">
                  <div
                    tabIndex={0}
                    aria-label={`${d.label}: ${seriesA} ${formatMoney(d.a)}, ${seriesB} ${formatMoney(d.b)}${d.note ? `, ${d.note}` : ""}`}
                    className="group relative flex h-full w-full items-end justify-center gap-[2px]"
                  >
                    {mode === "grouped" ? (
                      <>
                        <span className="w-full max-w-7 rounded-t-[4px] bg-series-1" style={{ height: `${pct(d.a)}%` }} />
                        <span className="w-full max-w-7 rounded-t-[4px] bg-series-2" style={{ height: `${pct(d.b)}%` }} />
                      </>
                    ) : (
                      <span className="flex h-full w-full max-w-8 flex-col justify-end gap-[2px]">
                        <span className="w-full rounded-t-[4px] bg-series-2" style={{ height: `${pct(d.b)}%` }} />
                        <span className="w-full bg-series-1" style={{ height: `${pct(d.a)}%` }} />
                      </span>
                    )}
                    <Tooltip>
                      <span className="font-semibold">{d.label}</span>
                      <br />
                      {seriesA}: {formatMoney(d.a)}
                      <br />
                      {seriesB}: {formatMoney(d.b)}
                      {d.note ? (
                        <>
                          <br />
                          <span className="text-muted">{d.note}</span>
                        </>
                      ) : null}
                    </Tooltip>
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <ul className={cx("mt-1.5 flex text-[11px] text-muted", data.length > 12 ? "gap-[2px]" : "gap-3 sm:gap-6")} aria-hidden="true">
            {data.map((d, index) => (
              <li key={d.key} className="min-w-0 flex-1 truncate text-center">
                {index % labelEvery === 0 ? (d.axisLabel ?? d.label) : ""}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <TableView caption={caption} headers={["Period", seriesA, seriesB]} rows={data.map((d) => [d.label + (d.note ? ` (${d.note})` : ""), formatMoney(d.a), formatMoney(d.b)])} />
    </figure>
  );
}

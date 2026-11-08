import Link from "next/link";
import { cx } from "./primitives";

/** Builds `path?query` keeping existing filters and replacing `page`. */
export function hrefWithParams(path: string, params: Record<string, string | undefined>, overrides: Record<string, string | undefined> = {}): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries({ ...params, ...overrides })) {
    if (value !== undefined && value !== "") query.set(key, value);
  }
  const text = query.toString();
  return text ? `${path}?${text}` : path;
}

/** Page numbers to show: first, last, and a window around the current page. */
function visiblePages(current: number, count: number): Array<number | "gap"> {
  const pages = new Set([1, count, current - 1, current, current + 1].filter((p) => p >= 1 && p <= count));
  const sorted = [...pages].sort((a, b) => a - b);
  const result: Array<number | "gap"> = [];
  for (const page of sorted) {
    const previous = result.at(-1);
    if (typeof previous === "number" && page - previous > 1) result.push("gap");
    result.push(page);
  }
  return result;
}

export function Pagination({
  path,
  params,
  page,
  pageCount,
  label,
}: {
  path: string;
  params: Record<string, string | undefined>;
  page: number;
  pageCount: number;
  label: string;
}) {
  if (pageCount <= 1) return null;
  const link = "inline-flex min-h-9 min-w-9 items-center justify-center rounded-lg px-2 text-sm";
  const pageHref = (target: number) => hrefWithParams(path, params, { page: target === 1 ? undefined : String(target) });
  return (
    <nav aria-label={label} className="flex flex-wrap items-center justify-between gap-2">
      {page > 1 ? (
        <Link href={pageHref(page - 1)} className={cx(link, "border border-border-strong hover:bg-surface-muted")} scroll={false}>
          <span aria-hidden="true">←</span>&nbsp;Previous
        </Link>
      ) : (
        <span className={cx(link, "border border-border text-muted")} aria-disabled="true">
          <span aria-hidden="true">←</span>&nbsp;Previous
        </span>
      )}
      <ol className="hidden items-center gap-1 sm:flex">
        {visiblePages(page, pageCount).map((item, index) =>
          item === "gap" ? (
            <li key={`gap-${index}`} aria-hidden="true" className="px-1 text-muted">
              …
            </li>
          ) : (
            <li key={item}>
              <Link
                href={pageHref(item)}
                scroll={false}
                aria-current={item === page ? "page" : undefined}
                aria-label={`Page ${item}`}
                className={cx(link, item === page ? "bg-primary font-semibold text-primary-contrast" : "hover:bg-surface-muted")}
              >
                {item}
              </Link>
            </li>
          ),
        )}
      </ol>
      <span className="text-sm text-muted sm:hidden">
        Page {page} of {pageCount}
      </span>
      {page < pageCount ? (
        <Link href={pageHref(page + 1)} className={cx(link, "border border-border-strong hover:bg-surface-muted")} scroll={false}>
          Next&nbsp;<span aria-hidden="true">→</span>
        </Link>
      ) : (
        <span className={cx(link, "border border-border text-muted")} aria-disabled="true">
          Next&nbsp;<span aria-hidden="true">→</span>
        </span>
      )}
    </nav>
  );
}

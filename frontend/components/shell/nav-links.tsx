"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cx } from "@/components/ui/primitives";
import { NavIcon } from "./nav-icon";
import { NAV_ITEMS, isActive } from "./nav-items";

const LINK = "flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors";

/**
 * Active-aware navigation. `usePathname` cannot resolve during prerendering
 * on routes with unknown dynamic params, so callers wrap this in <Suspense>
 * with <StaticNavLinks /> as the fallback.
 */
export function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <ul className="space-y-1">
      {NAV_ITEMS.map((item) => {
        const active = isActive(item.href, pathname);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cx(LINK, active ? "bg-primary-soft text-primary" : "text-muted hover:bg-surface-muted hover:text-text")}
            >
              <NavIcon href={item.href} />
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/** Same links without active state: the prerendered fallback. */
export function StaticNavLinks() {
  return (
    <ul className="space-y-1">
      {NAV_ITEMS.map((item) => (
        <li key={item.href}>
          <Link href={item.href} className={cx(LINK, "text-muted hover:bg-surface-muted hover:text-text")}>
            <NavIcon href={item.href} />
            {item.label}
          </Link>
        </li>
      ))}
    </ul>
  );
}

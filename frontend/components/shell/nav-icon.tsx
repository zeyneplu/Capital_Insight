import type { NavItem } from "./nav-items";

/**
 * Inline SVG icons: unlike Unicode symbols they do not depend on which glyphs
 * the font happens to include, and they inherit the link color.
 */
const PATHS: Record<NavItem["href"], string> = {
  "/": "M3 3h7v9H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 16h7v5H3z",
  "/accounts": "M3 9l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18",
  "/loans": "M12 3v18M17 7.5c0-1.9-2.2-3-5-3s-5 1.1-5 3 2.2 2.7 5 3.4 5 1.6 5 3.6-2.2 3-5 3-5-1.1-5-3",
  "/mortgages": "M3 11l9-7 9 7M5 10v10h14V10M10 20v-6h4v6",
  "/insights": "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z",
  "/connect": "M7 7h11l-3-3M17 17H6l3 3",
};

export function NavIcon({ href }: { href: NavItem["href"] }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
      <path d={PATHS[href]} />
    </svg>
  );
}

export interface NavItem {
  href: "/" | "/accounts" | "/loans" | "/mortgages" | "/insights" | "/connect";
  label: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/", label: "Overview" },
  { href: "/accounts", label: "Accounts" },
  { href: "/loans", label: "Loans" },
  { href: "/mortgages", label: "Mortgages" },
  { href: "/insights", label: "Insights" },
  { href: "/connect", label: "Connections" },
];

export function isActive(href: NavItem["href"], pathname: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

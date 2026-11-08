import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { Suspense } from "react";
import { MobileMenu } from "@/components/shell/mobile-menu";
import { NavLinks, StaticNavLinks } from "@/components/shell/nav-links";
import { DemoBadge } from "@/components/ui/primitives";
import { resetDemoAction } from "@/lib/actions/demo";
import { dataSourceKind } from "@/lib/data";
import { SNAPSHOT_DATE } from "@/lib/data/fixtures/institutions";
import { formatDate } from "@/lib/format";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: { default: "Capital Insight", template: "%s · Capital Insight" },
  description: "See your bank accounts, cards, loans and mortgage in one place. HackUTD 2026 demo with fictional data.",
};

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
      <span aria-hidden="true" className="grid size-8 place-items-center rounded-lg bg-primary text-sm text-primary-contrast">
        CI
      </span>
      Capital Insight
    </Link>
  );
}

function DataSourceBanner() {
  const kind = dataSourceKind();
  return kind === "mock" ? (
    <div className="border-b border-demo/20 bg-demo-soft px-4 py-2 text-xs text-demo sm:text-sm">
      <p className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-semibold">◆ Demo data</span>
        <span>Fictional records, fixed snapshot of {formatDate(SNAPSHOT_DATE)}. Connections and applications are simulated.</span>
      </p>
    </div>
  ) : (
    <div className="border-b border-border bg-surface-muted px-4 py-2 text-xs text-muted sm:text-sm">
      <p className="mx-auto max-w-7xl">Live data source: Capital Insight backend.</p>
    </div>
  );
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a href="#main" className="sr-only z-50 rounded-lg bg-primary px-4 py-2 text-primary-contrast focus:not-sr-only focus:fixed focus:left-3 focus:top-3">
          Skip to main content
        </a>
        <DataSourceBanner />
        <header className="relative border-b border-border bg-surface">
          <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-3 px-4">
            <div className="flex items-center gap-3">
              <Brand />
              <span className="hidden sm:inline">
                <DemoBadge />
              </span>
            </div>
            <MobileMenu />
          </div>
        </header>
        <div className="mx-auto flex w-full max-w-7xl flex-1 gap-8 px-4 py-6 lg:py-8">
          <nav aria-label="Main" className="hidden w-52 shrink-0 lg:block">
            <div className="sticky top-6">
              <Suspense fallback={<StaticNavLinks />}>
                <NavLinks />
              </Suspense>
            </div>
          </nav>
          <main id="main" className="min-w-0 flex-1" tabIndex={-1}>
            {children}
          </main>
        </div>
        <footer className="border-t border-border bg-surface">
          <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-5 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
            <p>
              HackUTD 2026 demo. All institutions, people and records are fictional. Nothing here is financial advice, and no money moves.
            </p>
            <form action={resetDemoAction}>
              <button type="submit" className="font-medium text-primary underline-offset-4 hover:underline">
                Reset demo session
              </button>
            </form>
          </div>
        </footer>
      </body>
    </html>
  );
}

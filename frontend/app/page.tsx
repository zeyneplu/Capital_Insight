import { Suspense } from "react";
import { DashboardContent, DashboardSkeleton } from "@/components/dashboard/dashboard-content";
import { PageHeader } from "@/components/ui/primitives";

/**
 * The heading is static and prerenders into the shell. Everything that reads
 * the session (cookies) streams in behind <Suspense>, as Cache Components requires.
 */
export default function OverviewPage() {
  return (
    <>
      <PageHeader title="Overview" description="Your connected accounts, loans and mortgage in one place." />
      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardContent />
      </Suspense>
    </>
  );
}

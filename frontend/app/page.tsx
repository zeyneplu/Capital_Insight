import { Suspense } from "react";
import { DashboardContent, DashboardSkeleton } from "@/components/dashboard/dashboard-content";
import { Landing } from "@/components/landing/landing";
import { PageHeader } from "@/components/ui/primitives";
import { currentAppUser } from "@/lib/auth";
import { dataSourceKind } from "@/lib/data";

function Overview() {
  return (
    <>
      <PageHeader title="Overview" description="Your connected accounts, loans and mortgage in one place." />
      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardContent />
      </Suspense>
    </>
  );
}

/**
 * Live mode: signed-out visitors get the landing page, verified users their Overview.
 * Demo (fixture) mode needs no account, so it always shows the Overview.
 * Reading the session cookie happens behind <Suspense>, as Cache Components requires.
 */
async function Home() {
  if (dataSourceKind() !== "http") return <Overview />;
  let signedIn = false;
  try {
    signedIn = Boolean((await currentAppUser())?.email_verified_at);
  } catch {
    signedIn = false; // backend unreachable: the landing page still renders; sign-in reports the error
  }
  return signedIn ? <Overview /> : <Landing />;
}

export default function HomePage() {
  return (
    <Suspense fallback={<DashboardSkeleton />}>
      <Home />
    </Suspense>
  );
}

import type { Metadata } from "next";
import { Suspense } from "react";
import { PlanningGate } from "@/components/planning/planning-gate";
import { PlanningHub } from "@/components/planning/planning-hub";
import { LoadingBlock, PageHeader, Skeleton } from "@/components/ui/primitives";
import { loadPlanningOverview } from "@/lib/planning-server";

export const metadata: Metadata = { title: "Plan & goals" };

async function PlanningContent() {
  const result = await loadPlanningOverview();
  if (result.status !== "ok") return <PlanningGate result={result} feature="Planning" />;
  return <PlanningHub initial={result.data} />;
}

export default function PlanningPage() {
  return (
    <>
      <PageHeader title="Plan & goals" description="Set targets for education, a car, retirement or better credit habits, then explore the numbers." />
      <Suspense
        fallback={
          <LoadingBlock label="Loading your plan">
            <div className="space-y-4">
              <Skeleton className="h-52" />
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {[0, 1, 2, 3].map((key) => (
                  <Skeleton key={key} className="h-24" />
                ))}
              </div>
              <Skeleton className="h-64" />
            </div>
          </LoadingBlock>
        }
      >
        <PlanningContent />
      </Suspense>
    </>
  );
}

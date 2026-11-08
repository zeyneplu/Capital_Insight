import type { Metadata } from "next";
import { Suspense } from "react";
import { PlanningGate } from "@/components/planning/planning-gate";
import { SamChat } from "@/components/planning/sam-chat";
import { LoadingBlock, PageHeader, Skeleton } from "@/components/ui/primitives";
import { loadPlanningOverview, loadSamHistory } from "@/lib/planning-server";

export const metadata: Metadata = { title: "Ask Sam" };

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

async function SamContent({ searchParams }: { searchParams: SearchParams }) {
  const [overview, history, params] = await Promise.all([loadPlanningOverview(), loadSamHistory(), searchParams]);
  if (overview.status !== "ok") return <PlanningGate result={overview} feature="Sam" />;
  const prompt = typeof params.prompt === "string" ? params.prompt.slice(0, 500) : "";
  return <SamChat overview={overview.data} history={history.status === "ok" ? history.data : []} initialPrompt={prompt} />;
}

export default function SamPage({ searchParams }: { searchParams: SearchParams }) {
  return (
    <>
      <PageHeader title="Ask Sam" description="Your personal-finance assistant. Ask about budgets, debt, credit habits, savings goals and big purchases." />
      <Suspense
        fallback={
          <LoadingBlock label="Loading Sam">
            <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
              <Skeleton className="h-[32rem]" />
              <Skeleton className="h-80" />
            </div>
          </LoadingBlock>
        }
      >
        <SamContent searchParams={searchParams} />
      </Suspense>
    </>
  );
}

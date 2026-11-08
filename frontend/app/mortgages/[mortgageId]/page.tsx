import type { Metadata } from "next";
import { Suspense } from "react";
import { SchedulePageBody } from "@/components/lending/schedule-page";
import { LoadingBlock, Skeleton, TextLink } from "@/components/ui/primitives";
import { getDataProvider } from "@/lib/data";
import { parsePage, type SearchParams } from "@/lib/search-params";

export const metadata: Metadata = { title: "Mortgage schedule" };

async function MortgageSchedule({ params, searchParams }: { params: Promise<{ mortgageId: string }>; searchParams: Promise<SearchParams> }) {
  const [{ mortgageId }, query] = await Promise.all([params, searchParams]);
  const result = await getDataProvider().getMortgageSchedule(mortgageId);
  return (
    <SchedulePageBody result={result} page={parsePage(query)} path={`/mortgages/${encodeURIComponent(mortgageId)}`} connectHref="/connect?institution=mortgages" />
  );
}

export default function MortgageSchedulePage({ params, searchParams }: PageProps<"/mortgages/[mortgageId]">) {
  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-4 text-sm">
        <TextLink href="/mortgages">
          <span aria-hidden="true">← </span>All mortgages
        </TextLink>
      </nav>
      <Suspense
        fallback={
          <LoadingBlock label="Loading amortization schedule">
            <div className="space-y-6">
              <Skeleton className="h-16 w-72 max-w-full" />
              <Skeleton className="h-28" />
              <Skeleton className="h-96" />
            </div>
          </LoadingBlock>
        }
      >
        <MortgageSchedule params={params} searchParams={searchParams} />
      </Suspense>
    </>
  );
}

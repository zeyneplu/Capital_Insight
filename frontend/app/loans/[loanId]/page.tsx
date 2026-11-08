import type { Metadata } from "next";
import { Suspense } from "react";
import { SchedulePageBody } from "@/components/lending/schedule-page";
import { LoadingBlock, Skeleton, TextLink } from "@/components/ui/primitives";
import { getDataProvider } from "@/lib/data";
import { parsePage, type SearchParams } from "@/lib/search-params";

export const metadata: Metadata = { title: "Loan schedule" };

async function LoanSchedule({ params, searchParams }: { params: Promise<{ loanId: string }>; searchParams: Promise<SearchParams> }) {
  const [{ loanId }, query] = await Promise.all([params, searchParams]);
  const result = await getDataProvider().getLoanSchedule(loanId);
  return <SchedulePageBody result={result} page={parsePage(query)} path={`/loans/${encodeURIComponent(loanId)}`} connectHref="/connect?institution=loans" />;
}

export default function LoanSchedulePage({ params, searchParams }: PageProps<"/loans/[loanId]">) {
  return (
    <>
      <nav aria-label="Breadcrumb" className="mb-4 text-sm">
        <TextLink href="/loans">
          <span aria-hidden="true">← </span>All loans
        </TextLink>
      </nav>
      <Suspense
        fallback={
          <LoadingBlock label="Loading repayment schedule">
            <div className="space-y-6">
              <Skeleton className="h-16 w-72 max-w-full" />
              <Skeleton className="h-28" />
              <Skeleton className="h-96" />
            </div>
          </LoadingBlock>
        }
      >
        <LoanSchedule params={params} searchParams={searchParams} />
      </Suspense>
    </>
  );
}

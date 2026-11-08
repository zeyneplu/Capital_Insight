import type { Metadata } from "next";
import { Suspense } from "react";
import { ActiveRecordCard, ApplicationHistory, OffersTable } from "@/components/lending/applications";
import { LoanApplicationForm } from "@/components/lending/loan-form";
import { Alert, ButtonLink, Card, EmptyState, LoadingBlock, PageHeader, Skeleton } from "@/components/ui/primitives";
import { getDataProvider } from "@/lib/data";

export const metadata: Metadata = { title: "Loans" };

async function LoansContent() {
  const provider = getDataProvider();
  const [gated, offers] = await Promise.all([provider.listLoanApplications(), provider.listLoanOffers()]);
  const applications = gated.connected ? gated.data : [];
  const active = applications.filter((application) => application.status === "approved");

  return (
    <div className="space-y-6">
      {!gated.connected ? (
        <Alert tone="info" title={`${gated.institution.name} is not connected`}>
          <p>Connect it to see your loans and submit simulated applications. Public offers are shown below.</p>
          <ButtonLink href="/connect?institution=loans" size="sm" className="mt-2">
            Connect {gated.institution.shortName}
          </ButtonLink>
        </Alert>
      ) : (
        <section aria-labelledby="active-loans">
          <h2 id="active-loans" className="mb-3 text-lg font-semibold">
            Your loans
          </h2>
          {active.length ? (
            <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {active.map((application) => (
                <li key={application.id}>
                  <ActiveRecordCard application={application} />
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No approved loans" description="Approved applications appear here with a projected repayment schedule." />
          )}
        </section>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <Card
          className="xl:col-span-3"
          title="Apply for a simulated loan"
          description="Uses fictional decision rules: a 620 minimum score and a 40% monthly debt-to-income limit. No credit check, and no money is disbursed."
        >
          <LoanApplicationForm offers={offers} connected={gated.connected} />
        </Card>
        <Card className="xl:col-span-2" title="Offers" description="Public product list from the lender.">
          <OffersTable offers={offers} />
        </Card>
      </div>

      {gated.connected ? (
        <Card title="Application history" description="Approved and declined applications, newest first. Applications from this demo session are kept in this browser only.">
          <ApplicationHistory applications={applications} />
        </Card>
      ) : null}
    </div>
  );
}

function LoansSkeleton() {
  return (
    <LoadingBlock label="Loading loans">
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Skeleton className="h-52" />
          <Skeleton className="h-52" />
        </div>
        <Skeleton className="h-96" />
      </div>
    </LoadingBlock>
  );
}

export default function LoansPage() {
  return (
    <>
      <PageHeader title="Loans" description="Simulated personal and auto loans from Capital Insight Mock Loans." />
      <Suspense fallback={<LoansSkeleton />}>
        <LoansContent />
      </Suspense>
    </>
  );
}

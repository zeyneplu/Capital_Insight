import type { Metadata } from "next";
import { Suspense } from "react";
import { ActiveRecordCard, ApplicationHistory, OffersTable } from "@/components/lending/applications";
import { MortgageApplicationForm } from "@/components/lending/mortgage-form";
import { Alert, ButtonLink, Card, EmptyState, LoadingBlock, PageHeader, Skeleton } from "@/components/ui/primitives";
import { getDataProvider } from "@/lib/data";

export const metadata: Metadata = { title: "Mortgages" };

async function MortgagesContent() {
  const provider = getDataProvider();
  const [gated, offers] = await Promise.all([provider.listMortgageApplications(), provider.listMortgageOffers()]);
  const applications = gated.connected ? gated.data : [];
  const active = applications.filter((application) => application.status === "approved");
  const offer = offers[0];

  return (
    <div className="space-y-6">
      {!gated.connected ? (
        <Alert tone="info" title={`${gated.institution.name} is not connected`}>
          <p>Connect it to see your mortgage and submit simulated applications. Public offers are shown below.</p>
          <ButtonLink href="/connect?institution=mortgages" size="sm" className="mt-2">
            Connect {gated.institution.shortName}
          </ButtonLink>
        </Alert>
      ) : (
        <section aria-labelledby="active-mortgages">
          <h2 id="active-mortgages" className="mb-3 text-lg font-semibold">
            Your mortgages
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
            <EmptyState title="No approved mortgages" description="Approved applications appear here with an amortization schedule." />
          )}
        </section>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-5">
        <Card
          className="xl:col-span-3"
          title="Apply for a simulated mortgage"
          description="The lender calculates the financed amount from property value minus down payment. Fictional rules: 5% minimum down, 620 minimum score, 40% debt-to-income limit."
        >
          {offer ? <MortgageApplicationForm offer={offer} connected={gated.connected} /> : <EmptyState title="No mortgage offers available" />}
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

function MortgagesSkeleton() {
  return (
    <LoadingBlock label="Loading mortgages">
      <div className="space-y-6">
        <Skeleton className="h-52 md:w-1/2" />
        <Skeleton className="h-96" />
      </div>
    </LoadingBlock>
  );
}

export default function MortgagesPage() {
  return (
    <>
      <PageHeader title="Mortgages" description="Simulated fixed-rate mortgages from Capital Insight Mock Mortgages." />
      <Suspense fallback={<MortgagesSkeleton />}>
        <MortgagesContent />
      </Suspense>
    </>
  );
}

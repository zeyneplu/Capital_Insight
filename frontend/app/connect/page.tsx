import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { ConsentFlow } from "@/components/connect/consent-flow";
import { Alert, Badge, Button, ButtonLink, Card, LoadingBlock, PageHeader, Skeleton, TextLink } from "@/components/ui/primitives";
import { disconnectAction } from "@/lib/actions/connect";
import { getDataProvider } from "@/lib/data";
import { ACCOUNT_TYPE_LABELS } from "@/lib/format";
import { firstParam, type SearchParams } from "@/lib/search-params";
import type { AccountType, Connection } from "@/lib/types";

export const metadata: Metadata = { title: "Connections" };

const SERVICE_LABEL = { mock_bank: "Bank", mock_loan: "Lender", mock_mortgage: "Mortgage lender" } as const;

function DisconnectButton({ institutionId, name }: { institutionId: string; name: string }) {
  return (
    <form action={disconnectAction}>
      <input type="hidden" name="institutionId" value={institutionId} />
      <Button type="submit" variant="danger" size="sm" aria-label={`Disconnect ${name}`}>
        Disconnect
      </Button>
    </form>
  );
}

function InstitutionCard({ connection }: { connection: Connection }) {
  const { institution, connected, customer } = connection;
  return (
    <article className="flex h-full flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">{institution.name}</h2>
          <p className="text-xs text-muted">{SERVICE_LABEL[institution.service]}</p>
        </div>
        {connected ? (
          <Badge tone="good">
            <span aria-hidden="true">●</span> Connected
          </Badge>
        ) : (
          <Badge>Not connected</Badge>
        )}
      </div>
      <p className="text-sm text-muted">{institution.description}</p>
      <p className="text-xs text-muted">
        Products: {institution.products.map((product) => ACCOUNT_TYPE_LABELS[product as AccountType] ?? product).join(", ")}
      </p>
      {connected && customer ? (
        <p className="text-xs text-muted">
          Signed in as {customer.email} <span className="font-mono">({customer.id})</span>
        </p>
      ) : null}
      <div className="mt-auto flex gap-2 pt-1">
        {connected ? (
          <DisconnectButton institutionId={institution.id} name={institution.name} />
        ) : (
          <ButtonLink href={`/connect?institution=${institution.id}`} size="sm">
            Connect
          </ButtonLink>
        )}
      </div>
    </article>
  );
}

async function ConnectContent({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const selectedId = firstParam(params, "institution");
  const provider = getDataProvider();
  const connections = await provider.listConnections();
  const selected = selectedId ? connections.find((connection) => connection.institution.id === selectedId) : undefined;

  if (selectedId && !selected) {
    return (
      <Alert tone="warn" role="alert" title="Unknown institution">
        “{selectedId}” is not an available institution. <TextLink href="/connect">See all institutions</TextLink>
      </Alert>
    );
  }

  if (selected) {
    const { institution } = selected;
    if (selected.connected) {
      return (
        <Card className="max-w-2xl">
          <Alert tone="good" role="status" title={`${institution.name} is connected`}>
            <p>
              Signed in as {selected.customer?.email}. Its data now appears across Capital Insight.
            </p>
          </Alert>
          <div className="mt-4 flex flex-wrap gap-2">
            <ButtonLink href={institution.service === "mock_bank" ? "/accounts" : institution.service === "mock_loan" ? "/loans" : "/mortgages"}>
              View {institution.service === "mock_bank" ? "accounts" : institution.service === "mock_loan" ? "loans" : "mortgages"}
            </ButtonLink>
            <ButtonLink href="/" variant="secondary">
              Go to overview
            </ButtonLink>
            <ButtonLink href="/connect" variant="ghost">
              Connect another
            </ButtonLink>
          </div>
        </Card>
      );
    }
    const step = await provider.getConsentStep(institution.id);
    return (
      <Card className="max-w-2xl">
        <p className="mb-4 text-sm">
          <Link href="/connect" className="font-medium text-primary hover:underline">
            <span aria-hidden="true">← </span>Choose a different institution
          </Link>
        </p>
        <ConsentFlow
          key={institution.id}
          institution={institution}
          initial={{ step: step?.step ?? "email", email: step?.email ?? institution.demoEmail }}
          demoCode={step?.demoCode}
        />
      </Card>
    );
  }

  const connectedCount = connections.filter((connection) => connection.connected).length;
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">
        {connectedCount} of {connections.length} institutions connected. Each connection is a separate consent with its own sign-in; Capital Insight
        never assumes two institutions share a customer.
      </p>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {connections.map((connection) => (
          <li key={connection.institution.id}>
            <InstitutionCard connection={connection} />
          </li>
        ))}
      </ul>
      <Alert tone="demo" title="How this demo stores connections">
        Connections and simulated applications are kept in a cookie in this browser for up to 7 days (the 5 most recent applications per lender).
        Use “Reset demo session” in the footer to start over.
      </Alert>
    </div>
  );
}

export default function ConnectPage({ searchParams }: PageProps<"/connect">) {
  return (
    <>
      <PageHeader title="Connections" description="Connect mock banks and lenders with a simulated consent flow. Nothing here signs in to a real institution." />
      <Suspense
        fallback={
          <LoadingBlock label="Loading institutions">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {[0, 1, 2, 3, 4, 5].map((key) => (
                <Skeleton key={key} className="h-48" />
              ))}
            </div>
          </LoadingBlock>
        }
      >
        <ConnectContent searchParams={searchParams} />
      </Suspense>
    </>
  );
}

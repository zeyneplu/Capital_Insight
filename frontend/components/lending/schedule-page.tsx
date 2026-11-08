import { notFound } from "next/navigation";
import { Alert, ButtonLink, StatusBadge, Badge } from "@/components/ui/primitives";
import type { Gated } from "@/lib/data";
import { LOAN_TYPE_LABELS, formatDate, formatMoney, formatTerm } from "@/lib/format";
import type { ScheduleResult } from "@/lib/types";
import { ScheduleView } from "./schedule-view";

/** Shared body of /loans/[loanId] and /mortgages/[mortgageId]. */
export function SchedulePageBody({ result, page, path, connectHref }: { result: Gated<ScheduleResult>; page: number; path: string; connectHref: string }) {
  if (!result.connected) {
    return (
      <Alert tone="info" title={`${result.institution.name} is not connected`}>
        <p>Connect it to view this repayment schedule.</p>
        <ButtonLink href={connectHref} size="sm" className="mt-2">
          Connect {result.institution.shortName}
        </ButtonLink>
      </Alert>
    );
  }
  const data = result.data;
  if (data.kind === "not_found") notFound();

  const application = data.application;
  const title = application.kind === "mortgage" ? "Fixed-rate mortgage" : LOAN_TYPE_LABELS[application.loanType];

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm text-muted">{application.lender.name}</p>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
          <p className="mt-1 text-sm text-muted">
            {formatMoney(application.amount)} · {formatTerm(application.termMonths)} · submitted {formatDate(application.createdAt)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={application.status} />
          {application.submittedThisSession ? <Badge tone="demo">Simulated · not funded</Badge> : <Badge tone="demo">◆ Demo data</Badge>}
        </div>
      </header>
      {data.kind === "declined" ? (
        <Alert tone="warn" role="status" title="No repayment schedule">
          <p>Declined applications have no schedule. Decision: {application.decisionReason}.</p>
        </Alert>
      ) : (
        <ScheduleView application={application} rows={data.rows} page={page} path={path} />
      )}
    </div>
  );
}

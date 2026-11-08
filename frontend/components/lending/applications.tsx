import Link from "next/link";
import { Money } from "@/components/ui/money";
import { Badge, EmptyState, StatusBadge } from "@/components/ui/primitives";
import { LOAN_TYPE_LABELS, formatDate, formatDateTime, formatMoney, formatRate, formatTerm } from "@/lib/format";
import type { LoanApplication, LoanOffer, MortgageApplication } from "@/lib/types";

type AnyApplication = LoanApplication | MortgageApplication;

const titleOf = (application: AnyApplication) => (application.kind === "mortgage" ? "Fixed-rate mortgage" : LOAN_TYPE_LABELS[application.loanType]);
export const scheduleHref = (application: AnyApplication) =>
  `/${application.kind === "mortgage" ? "mortgages" : "loans"}/${encodeURIComponent(application.id)}`;

/** An approved record. Original amount and projected payment only; never a live balance. */
export function ActiveRecordCard({ application }: { application: AnyApplication }) {
  const servicing = application.servicing;
  return (
    <article className="relative flex h-full flex-col gap-4 rounded-xl border border-border bg-surface p-4 focus-within:border-primary hover:border-border-strong">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">
            <Link href={scheduleHref(application)} className="after:absolute after:inset-0 after:content-['']">
              {titleOf(application)}
            </Link>
          </h3>
          <p className="text-xs text-muted">
            {application.lender.name} · since {formatDate(application.createdAt)}
          </p>
        </div>
        {application.submittedThisSession ? <Badge tone="demo">Simulated · not funded</Badge> : <StatusBadge status="approved" />}
      </div>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-muted">Amount financed</dt>
          <dd className="font-semibold tabular-nums">{formatMoney(application.amount)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Principal + interest</dt>
          <dd className="font-semibold tabular-nums">{formatMoney(application.monthlyPayment)}/mo</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">APR</dt>
          <dd className="tabular-nums">{formatRate(application.apr)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Term</dt>
          <dd>{formatTerm(application.termMonths)}</dd>
        </div>
      </dl>
      {servicing ? (
        <p className="mt-auto rounded-lg bg-demo-soft p-2.5 text-xs text-demo">
          Demo servicing snapshot: about <Money value={servicing.estimatedOutstanding} className="font-semibold" /> left as of{" "}
          {formatDate(servicing.asOf)}, assuming scheduled payments were made.
        </p>
      ) : application.submittedThisSession ? (
        <p className="mt-auto text-xs text-muted">Approved in this demo session. No money is disbursed and it is not counted as debt.</p>
      ) : null}
      <span className="text-sm font-medium text-primary" aria-hidden="true">
        View repayment schedule →
      </span>
    </article>
  );
}

export function ApplicationHistory({ applications }: { applications: AnyApplication[] }) {
  if (applications.length === 0) return <EmptyState title="No applications yet" description="Applications you submit will appear here." />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] text-left text-sm">
        <caption className="sr-only">Application history, newest first</caption>
        <thead>
          <tr className="border-b border-border text-xs text-muted">
            <th scope="col" className="py-2 pr-3 font-medium">Submitted</th>
            <th scope="col" className="py-2 pr-3 font-medium">Product</th>
            <th scope="col" className="py-2 pr-3 text-right font-medium">Amount</th>
            <th scope="col" className="py-2 pr-3 font-medium">Decision</th>
            <th scope="col" className="py-2 font-medium">Reason</th>
          </tr>
        </thead>
        <tbody>
          {applications.map((application) => (
            <tr key={application.id} className="border-b border-border align-top last:border-0">
              <td className="py-2.5 pr-3 whitespace-nowrap text-muted">
                {application.submittedThisSession ? formatDateTime(application.createdAt) : formatDate(application.createdAt)}
              </td>
              <td className="py-2.5 pr-3">
                {application.status === "approved" ? (
                  <Link href={scheduleHref(application)} className="font-medium text-primary hover:underline">
                    {titleOf(application)}
                  </Link>
                ) : (
                  <span className="font-medium">{titleOf(application)}</span>
                )}
                <span className="block text-xs text-muted">{formatTerm(application.termMonths)}</span>
              </td>
              <td className="py-2.5 pr-3 text-right tabular-nums">{formatMoney(application.amount)}</td>
              <td className="py-2.5 pr-3">
                <span className="flex flex-col items-start gap-1">
                  <StatusBadge status={application.status} />
                  {application.submittedThisSession ? <Badge tone="demo">This session</Badge> : null}
                </span>
              </td>
              <td className="py-2.5 text-muted">{application.decisionReason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OffersTable({ offers }: { offers: LoanOffer[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[32rem] text-left text-sm">
        <caption className="sr-only">Available simulated products</caption>
        <thead>
          <tr className="border-b border-border text-xs text-muted">
            <th scope="col" className="py-2 pr-3 font-medium">Product</th>
            <th scope="col" className="py-2 pr-3 font-medium">Amount range</th>
            <th scope="col" className="py-2 pr-3 text-right font-medium">APR</th>
            <th scope="col" className="py-2 font-medium">Terms</th>
          </tr>
        </thead>
        <tbody>
          {offers.map((offer) => (
            <tr key={offer.loanType + offer.name} className="border-b border-border last:border-0">
              <th scope="row" className="py-2.5 pr-3 font-medium">
                {offer.name} {offer.simulated ? <Badge tone="demo" className="ml-1">Simulated</Badge> : null}
              </th>
              <td className="py-2.5 pr-3 tabular-nums">
                {formatMoney(offer.minimumAmount, { whole: true })} – {formatMoney(offer.maximumAmount, { whole: true })}
              </td>
              <td className="py-2.5 pr-3 text-right tabular-nums">{formatRate(offer.apr)}</td>
              <td className="py-2.5">{offer.termsMonths.map(formatTerm).join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

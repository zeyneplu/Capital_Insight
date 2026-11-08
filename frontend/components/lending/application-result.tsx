"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { Alert, StatusBadge, buttonClass } from "@/components/ui/primitives";
import { formatMoney, formatRate, formatTerm } from "@/lib/format";
import type { FieldError } from "@/lib/finance/underwriting";
import type { LoanApplication, MortgageApplication } from "@/lib/types";

type State =
  | { kind: "idle" }
  | { kind: "error"; status: 401 | 422; errors: FieldError[] }
  | { kind: "submitted"; application: LoanApplication | MortgageApplication };

/**
 * Announces the outcome of a submission and moves focus to it. A 201 can
 * still be a decline, so the decision is read from `status`, never assumed.
 */
export function ApplicationResult({ state, connectHref }: { state: State; connectHref: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (state.kind !== "idle") ref.current?.focus();
  }, [state]);

  if (state.kind === "idle") return null;

  if (state.kind === "error") {
    const general = state.errors.filter((error) => error.field === null);
    return (
      <div ref={ref} tabIndex={-1} className="outline-none">
        <Alert tone="bad" role="alert" title={state.status === 401 ? "Connection required" : "Please fix the highlighted fields"}>
          {general.length ? (
            <ul className="list-disc pl-4">
              {general.map((error) => (
                <li key={error.message}>{error.message}</li>
              ))}
            </ul>
          ) : (
            <p>{state.errors.length} field{state.errors.length === 1 ? "" : "s"} need attention.</p>
          )}
          {state.status === 401 ? (
            <Link href={connectHref} className="mt-2 inline-block font-medium underline">
              Connect now
            </Link>
          ) : null}
        </Alert>
      </div>
    );
  }

  const { application } = state;
  const approved = application.status === "approved";
  const href = `/${application.kind === "mortgage" ? "mortgages" : "loans"}/${encodeURIComponent(application.id)}`;
  return (
    <div ref={ref} tabIndex={-1} className="outline-none" role="status">
      <div className={`rounded-xl border p-4 ${approved ? "border-good/30 bg-good-soft" : "border-bad/30 bg-bad-soft"}`}>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={application.status} />
          <span className="text-xs text-muted">Simulated decision · no credit check · no money moves</span>
        </div>
        <p className="mt-2 font-semibold">{approved ? "Your simulated application was approved." : "Your simulated application was declined."}</p>
        <p className="text-sm">{application.decisionReason}.</p>
        <p className="mt-2 text-sm tabular-nums">
          {formatMoney(application.amount)} over {formatTerm(application.termMonths)} at {formatRate(application.apr)} APR: {formatMoney(application.monthlyPayment)}/month
          principal and interest.
        </p>
        {approved ? (
          <Link href={href} className={`${buttonClass("primary", "sm")} mt-3`}>
            View repayment schedule
          </Link>
        ) : (
          <p className="mt-2 text-xs text-muted">Declined applications have no repayment schedule. Adjust the amount, term or debt and try again.</p>
        )}
      </div>
    </div>
  );
}

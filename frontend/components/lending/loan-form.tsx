"use client";

import { useActionState, useState } from "react";
import { Field, Input, Select } from "@/components/ui/form";
import { Button, cx } from "@/components/ui/primitives";
import { submitLoanAction, type ApplicationFormState } from "@/lib/actions/applications";
import { monthlyPaymentCents } from "@/lib/finance/amortization";
import { fromCents, isMoneyString, toCents } from "@/lib/finance/money";
import { debtToIncomeForDisplay } from "@/lib/finance/underwriting";
import { LOAN_TYPE_LABELS, formatMoney, formatRate, formatRatio, formatTerm } from "@/lib/format";
import type { LoanApplication, LoanOffer } from "@/lib/types";
import { ApplicationResult } from "./application-result";

const DEFAULTS = { loan_type: "personal_loan", amount: "10000", term_months: "36", annual_income: "72000", existing_monthly_debt: "300", credit_score: "720" };
const clean = (value: string) => value.trim().replace(/,/g, "");
const money = (value: string) => (isMoneyString(clean(value)) && !clean(value).startsWith("-") ? toCents(clean(value)) : null);

export function LoanApplicationForm({ offers, connected }: { offers: LoanOffer[]; connected: boolean }) {
  const [state, formAction, pending] = useActionState<ApplicationFormState<LoanApplication>, FormData>(submitLoanAction, { kind: "idle", values: DEFAULTS });
  const [values, setValues] = useState<Record<string, string>>(DEFAULTS);
  const set = (key: string) => (event: { target: { value: string } }) => setValues((current) => ({ ...current, [key]: event.target.value }));

  const offer = offers.find((candidate) => candidate.loanType === values.loan_type) ?? offers[0];
  const errorFor = (field: string) => (state.kind === "error" ? state.errors.find((error) => error.field === field)?.message : undefined);

  // Live, exact preview with the same arithmetic the lender uses.
  const amount = money(values.amount);
  const income = money(values.annual_income);
  const debt = money(values.existing_monthly_debt);
  const term = Number(values.term_months);
  const inRange = amount !== null && amount >= toCents(offer.minimumAmount) && amount <= toCents(offer.maximumAmount);
  const payment = inRange && offer.termsMonths.includes(term) ? monthlyPaymentCents(amount, offer.apr, term) : null;
  const dti = payment !== null && income !== null && income > 0n && debt !== null ? debtToIncomeForDisplay(debt, payment, income) : null;

  const changeProduct = (event: { target: { value: string } }) => {
    const next = offers.find((candidate) => candidate.loanType === event.target.value) ?? offers[0];
    setValues((current) => ({
      ...current,
      loan_type: next.loanType,
      term_months: next.termsMonths.includes(Number(current.term_months)) ? current.term_months : String(next.termsMonths[Math.floor(next.termsMonths.length / 2)]),
    }));
  };

  const control = (field: string, describedBy: string | undefined, invalid: boolean) => ({
    id: `loan-${field}`,
    name: field,
    value: values[field],
    onChange: set(field),
    "aria-describedby": describedBy,
    "aria-invalid": invalid || undefined,
  });

  return (
    <form action={formAction} className="space-y-5" noValidate>
      <fieldset disabled={!connected || pending} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <legend className="sr-only">Loan details</legend>
        <Field id="loan-loan_type" label="Product" error={errorFor("loan_type")}>
          {(describedBy, invalid) => (
            <Select {...control("loan_type", describedBy, invalid)} onChange={changeProduct}>
              {offers.map((candidate) => (
                <option key={candidate.loanType} value={candidate.loanType}>
                  {LOAN_TYPE_LABELS[candidate.loanType]} · {formatRate(candidate.apr)} APR
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field id="loan-term_months" label="Term" error={errorFor("term_months")}>
          {(describedBy, invalid) => (
            <Select {...control("term_months", describedBy, invalid)}>
              {offer.termsMonths.map((months) => (
                <option key={months} value={months}>
                  {formatTerm(months)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field
          id="loan-amount"
          label="Amount (USD)"
          hint={`Between ${formatMoney(offer.minimumAmount, { whole: true })} and ${formatMoney(offer.maximumAmount, { whole: true })}`}
          error={errorFor("amount")}
        >
          {(describedBy, invalid) => <Input {...control("amount", describedBy, invalid)} inputMode="decimal" autoComplete="off" />}
        </Field>
        <Field id="loan-annual_income" label="Annual income (USD)" error={errorFor("annual_income")}>
          {(describedBy, invalid) => <Input {...control("annual_income", describedBy, invalid)} inputMode="decimal" autoComplete="off" />}
        </Field>
        <Field id="loan-existing_monthly_debt" label="Existing monthly debt payments (USD)" hint="Cards, loans, rent you are obligated to pay" error={errorFor("existing_monthly_debt")}>
          {(describedBy, invalid) => <Input {...control("existing_monthly_debt", describedBy, invalid)} inputMode="decimal" autoComplete="off" />}
        </Field>
        <Field id="loan-credit_score" label="Credit score (self-reported)" hint="300 to 850. No credit check is performed." error={errorFor("credit_score")}>
          {(describedBy, invalid) => <Input {...control("credit_score", describedBy, invalid)} inputMode="numeric" autoComplete="off" />}
        </Field>
      </fieldset>

      <div className="rounded-lg border border-border bg-surface-muted p-3 text-sm" aria-live="polite">
        <p className="text-xs font-medium text-muted">Estimate before you apply</p>
        {payment !== null ? (
          <p className="mt-1">
            <span className="text-lg font-semibold tabular-nums">{formatMoney(fromCents(payment))}</span>/month principal and interest
            {dti !== null ? (
              <span className={cx("ml-1", dti > 0.4 ? "text-bad" : "text-muted")}>
                · debt-to-income {formatRatio(dti, { whole: true })}
                {dti > 0.4 ? " (above the mock 40% limit)" : ""}
              </span>
            ) : null}
          </p>
        ) : (
          <p className="mt-1 text-muted">Enter an amount within the product range to see the monthly payment.</p>
        )}
      </div>

      <Button type="submit" disabled={!connected || pending}>
        {pending ? "Submitting…" : "Submit simulated application"}
      </Button>
      <ApplicationResult state={state} connectHref="/connect?institution=loans" />
    </form>
  );
}


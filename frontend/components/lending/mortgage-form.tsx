"use client";

import { useActionState, useState } from "react";
import { Field, Input } from "@/components/ui/form";
import { Button, cx } from "@/components/ui/primitives";
import { submitMortgageAction, type ApplicationFormState } from "@/lib/actions/applications";
import { monthlyPaymentCents } from "@/lib/finance/amortization";
import { fromCents, isMoneyString, ratioForDisplay, toCents } from "@/lib/finance/money";
import { debtToIncomeForDisplay, mortgageAmounts } from "@/lib/finance/underwriting";
import { formatMoney, formatRate, formatRatio, formatTerm } from "@/lib/format";
import type { LoanOffer, MortgageApplication } from "@/lib/types";
import { ApplicationResult } from "./application-result";

const DEFAULTS = { property_value: "350000", down_payment: "70000", term_months: "360", annual_income: "120000", existing_monthly_debt: "500", credit_score: "740" };
const clean = (value: string) => value.trim().replace(/,/g, "");
const money = (value: string) => (isMoneyString(clean(value)) && !clean(value).startsWith("-") ? toCents(clean(value)) : null);

export function MortgageApplicationForm({ offer, connected }: { offer: LoanOffer; connected: boolean }) {
  const [state, formAction, pending] = useActionState<ApplicationFormState<MortgageApplication>, FormData>(submitMortgageAction, { kind: "idle", values: DEFAULTS });
  const [values, setValues] = useState<Record<string, string>>(DEFAULTS);
  const set = (key: string) => (event: { target: { value: string } }) => setValues((current) => ({ ...current, [key]: event.target.value }));
  const errorFor = (field: string) => (state.kind === "error" ? state.errors.find((error) => error.field === field)?.message : undefined);

  // The service calculates the financed amount; we mirror it for the preview.
  const property = money(values.property_value);
  const down = money(values.down_payment);
  const income = money(values.annual_income);
  const debt = money(values.existing_monthly_debt);
  const term = Number(values.term_months);
  const valid = property !== null && property > 0n && down !== null && down < property;
  const derived = valid ? mortgageAmounts(fromCents(property), fromCents(down)) : null;
  const financed = derived ? toCents(derived.amount) : null;
  const inRange = financed !== null && financed >= toCents(offer.minimumAmount) && financed <= toCents(offer.maximumAmount);
  const payment = inRange && offer.termsMonths.includes(term) ? monthlyPaymentCents(financed, offer.apr, term) : null;
  const downShare = valid ? ratioForDisplay(down, property) : null;
  const dti = payment !== null && income !== null && income > 0n && debt !== null ? debtToIncomeForDisplay(debt, payment, income) : null;

  const control = (field: string, describedBy: string | undefined, invalid: boolean) => ({
    id: `mortgage-${field}`,
    name: field,
    value: values[field],
    onChange: set(field),
    "aria-describedby": describedBy,
    "aria-invalid": invalid || undefined,
    inputMode: "decimal" as const,
    autoComplete: "off",
  });

  return (
    <form action={formAction} className="space-y-5" noValidate>
      <fieldset disabled={!connected || pending} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <legend className="sr-only">Mortgage details</legend>
        <Field id="mortgage-property_value" label="Property value (USD)" error={errorFor("property_value")}>
          {(describedBy, invalid) => <Input {...control("property_value", describedBy, invalid)} />}
        </Field>
        <Field
          id="mortgage-down_payment"
          label="Down payment (USD)"
          hint={downShare !== null ? `${formatRatio(downShare, { whole: downShare >= 0.1 })} of the property value. The mock minimum is 5%.` : "Must be less than the property value."}
          error={errorFor("down_payment")}
        >
          {(describedBy, invalid) => <Input {...control("down_payment", describedBy, invalid)} />}
        </Field>
        <fieldset className="sm:col-span-2">
          <legend className="mb-1.5 text-sm font-medium">Term</legend>
          <div className="flex flex-wrap gap-2">
            {offer.termsMonths.map((months) => (
              <label
                key={months}
                className={cx(
                  "inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-lg border px-3 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[var(--focus)]",
                  values.term_months === String(months) ? "border-primary bg-primary-soft font-medium text-primary" : "border-border-strong",
                )}
              >
                <input
                  type="radio"
                  name="term_months"
                  value={months}
                  checked={values.term_months === String(months)}
                  onChange={set("term_months")}
                  className="accent-[var(--primary)]"
                />
                {formatTerm(months)}
              </label>
            ))}
          </div>
          {errorFor("term_months") ? <p className="mt-1 text-xs font-medium text-bad">{errorFor("term_months")}</p> : null}
        </fieldset>
        <Field id="mortgage-annual_income" label="Annual income (USD)" error={errorFor("annual_income")}>
          {(describedBy, invalid) => <Input {...control("annual_income", describedBy, invalid)} />}
        </Field>
        <Field id="mortgage-existing_monthly_debt" label="Existing monthly debt payments (USD)" error={errorFor("existing_monthly_debt")}>
          {(describedBy, invalid) => <Input {...control("existing_monthly_debt", describedBy, invalid)} />}
        </Field>
        <Field id="mortgage-credit_score" label="Credit score (self-reported)" hint="300 to 850. No credit check is performed." error={errorFor("credit_score")}>
          {(describedBy, invalid) => <Input {...control("credit_score", describedBy, invalid)} inputMode="numeric" />}
        </Field>
      </fieldset>

      <div className="grid grid-cols-1 gap-3 rounded-lg border border-border bg-surface-muted p-3 text-sm sm:grid-cols-3" aria-live="polite">
        <div>
          <p className="text-xs font-medium text-muted">Amount financed</p>
          <p className="font-semibold tabular-nums">{derived ? formatMoney(derived.amount) : "—"}</p>
          {derived && !inRange ? (
            <p className="text-xs text-bad">
              Outside {formatMoney(offer.minimumAmount, { whole: true })}–{formatMoney(offer.maximumAmount, { whole: true })}
            </p>
          ) : null}
        </div>
        <div>
          <p className="text-xs font-medium text-muted">Loan-to-value</p>
          <p className="font-semibold tabular-nums">{derived ? formatRate(derived.loan_to_value) : "—"}</p>
        </div>
        <div>
          <p className="text-xs font-medium text-muted">Monthly principal + interest</p>
          <p className="font-semibold tabular-nums">{payment !== null ? formatMoney(fromCents(payment)) : "—"}</p>
          {dti !== null ? (
            <p className={cx("text-xs", dti > 0.4 ? "text-bad" : "text-muted")}>
              Debt-to-income {formatRatio(dti, { whole: true })}
              {dti > 0.4 ? " (above the mock 40% limit)" : ""}
            </p>
          ) : null}
        </div>
        <p className="text-xs text-muted sm:col-span-3">
          Estimate only, at {formatRate(offer.apr)} APR. Excludes property taxes, insurance, PMI, escrow and closing costs.
        </p>
      </div>

      <Button type="submit" disabled={!connected || pending}>
        {pending ? "Submitting…" : "Submit simulated application"}
      </Button>
      <ApplicationResult state={state} connectHref="/connect?institution=mortgages" />
    </form>
  );
}

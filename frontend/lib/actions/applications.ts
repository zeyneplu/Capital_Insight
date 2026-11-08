"use server";

import { getDataProvider } from "@/lib/data";
import type { FieldError } from "@/lib/finance/underwriting";
import type { LoanApplication, MortgageApplication } from "@/lib/types";

export type ApplicationFormState<T> =
  | { kind: "idle"; values: Record<string, string> }
  | { kind: "error"; status: 401 | 422; errors: FieldError[]; values: Record<string, string> }
  | { kind: "submitted"; application: T; values: Record<string, string> };

const LOAN_FIELDS = ["loan_type", "amount", "term_months", "annual_income", "existing_monthly_debt", "credit_score"] as const;
const MORTGAGE_FIELDS = ["property_value", "down_payment", "term_months", "annual_income", "existing_monthly_debt", "credit_score"] as const;

/** Copies only known fields, as bounded strings: the rest of the request is ignored. */
function readFields(form: FormData, fields: readonly string[]): Record<string, string> {
  return Object.fromEntries(fields.map((field) => [field, String(form.get(field) ?? "").slice(0, 32)]));
}

export async function submitLoanAction(
  previous: ApplicationFormState<LoanApplication>,
  form: FormData,
): Promise<ApplicationFormState<LoanApplication>> {
  const values = readFields(form, LOAN_FIELDS);
  const result = await getDataProvider().submitLoanApplication(values);
  return result.ok ? { kind: "submitted", application: result.application, values } : { kind: "error", status: result.status, errors: result.errors, values };
}

export async function submitMortgageAction(
  previous: ApplicationFormState<MortgageApplication>,
  form: FormData,
): Promise<ApplicationFormState<MortgageApplication>> {
  const values = readFields(form, MORTGAGE_FIELDS);
  const result = await getDataProvider().submitMortgageApplication(values);
  return result.ok ? { kind: "submitted", application: result.application, values } : { kind: "error", status: result.status, errors: result.errors, values };
}

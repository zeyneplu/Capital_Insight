"use server";

import { getDataProvider } from "@/lib/data";

/**
 * Consent-flow actions. Server Actions can be invoked by any direct POST, so
 * every input is read as bounded, untrusted text and checked by the provider.
 */
export interface ConsentFormState {
  step: "email" | "code";
  email: string;
  message?: string;
  error?: string;
  retryAfterSeconds?: number;
}

const text = (form: FormData, key: string, max: number) => String(form.get(key) ?? "").slice(0, max);

/** One action for the whole flow; the submit button's `intent` picks the step. */
export async function consentAction(previous: ConsentFormState, form: FormData): Promise<ConsentFormState> {
  const intent = text(form, "intent", 16);
  const institutionId = text(form, "institutionId", 40);
  const email = text(form, "email", 254).trim();
  const provider = getDataProvider();

  if (intent === "restart") return { step: "email", email };

  if (intent === "request") {
    const result = await provider.requestCode(institutionId, email);
    return result.ok
      ? { step: "code", email: email.toLowerCase(), message: result.message }
      : { step: previous.step, email, error: result.message, retryAfterSeconds: result.retryAfterSeconds };
  }

  if (intent === "verify") {
    const code = text(form, "code", 12).replace(/\s/g, "");
    const result = await provider.verifyCode(institutionId, email, code);
    // On success the session cookie changes and the page re-renders as connected.
    return result.ok ? { step: "code", email, message: `${result.institution.name} is connected.` } : { step: "code", email, error: result.message };
  }

  return { ...previous, error: "Unknown action." };
}

export async function disconnectAction(form: FormData): Promise<void> {
  await getDataProvider().disconnect(text(form, "institutionId", 40));
}

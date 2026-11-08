"use client";

import { useActionState, useEffect, useRef } from "react";
import { Field, Input } from "@/components/ui/form";
import { Alert, Button, cx } from "@/components/ui/primitives";
import { consentAction, type ConsentFormState } from "@/lib/actions/connect";
import type { ConnectableInstitution } from "@/lib/types";

const STEPS = ["Review access", "Verify", "Connected"] as const;

function Steps({ current }: { current: 0 | 1 | 2 }) {
  return (
    <ol className="mb-6 flex items-center gap-2 text-xs" aria-label="Connection progress">
      {STEPS.map((label, index) => (
        <li key={label} className="flex flex-1 items-center gap-2" aria-current={index === current ? "step" : undefined}>
          <span
            className={cx(
              "grid size-6 shrink-0 place-items-center rounded-full font-semibold",
              index < current ? "bg-good-soft text-good" : index === current ? "bg-primary text-primary-contrast" : "bg-surface-muted text-muted",
            )}
          >
            {index < current ? <span aria-label="done">✓</span> : index + 1}
          </span>
          <span className={cx("truncate", index === current ? "font-semibold" : "text-muted")}>{label}</span>
          {index < STEPS.length - 1 ? <span aria-hidden="true" className="h-px flex-1 bg-border" /> : null}
        </li>
      ))}
    </ol>
  );
}

function sharedData(institution: ConnectableInstitution): string[] {
  if (institution.service === "mock_bank") return ["Your profile name and email at this bank", "Account list, balances and account details", "Transaction history"];
  return ["Your profile name and email at this lender", "Your applications, decisions and projected schedules", "Permission to submit simulated applications for you"];
}

export function ConsentFlow({
  institution,
  initial,
  demoCode,
}: {
  institution: ConnectableInstitution;
  initial: ConsentFormState;
  /** Present only in fixture mode. */
  demoCode?: string;
}) {
  const [state, action, pending] = useActionState(consentAction, initial);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const firstRender = useRef(true);

  useEffect(() => {
    // Move focus to the step heading after each transition (not on first load).
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    headingRef.current?.focus();
  }, [state.step]);

  return (
    <div>
      <Steps current={state.step === "email" ? 0 : 1} />
      <form action={action} className="space-y-5">
        <input type="hidden" name="institutionId" value={institution.id} />
        {state.step === "email" ? (
          <>
            <h2 ref={headingRef} tabIndex={-1} className="text-lg font-semibold outline-none">
              Allow Capital Insight to read your {institution.name} data
            </h2>
            <div className="rounded-lg border border-border p-3">
              <p className="text-sm font-medium">What will be shared</p>
              <ul className="mt-2 space-y-1 text-sm text-muted">
                {sharedData(institution).map((item) => (
                  <li key={item} className="flex gap-2">
                    <span aria-hidden="true" className="text-good">
                      ✓
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-muted">Read-only. No payments, transfers or real funding. You can disconnect at any time.</p>
            </div>
            <Field id="consent-email" label="Email registered at this institution" hint={`Demo customer: ${institution.demoEmail}`}>
              {(describedBy) => (
                <Input id="consent-email" name="email" type="email" autoComplete="email" required defaultValue={state.email} aria-describedby={describedBy} />
              )}
            </Field>
            {state.error ? (
              <Alert tone="bad" role="alert" title="Could not send a code">
                {state.error}
                {state.retryAfterSeconds ? ` Try again in ${state.retryAfterSeconds} seconds.` : ""}
              </Alert>
            ) : null}
            <Button type="submit" name="intent" value="request" disabled={pending}>
              {pending ? "Sending…" : "Send verification code"}
            </Button>
          </>
        ) : (
          <>
            <h2 ref={headingRef} tabIndex={-1} className="text-lg font-semibold outline-none">
              Enter the six-digit code
            </h2>
            <input type="hidden" name="email" value={state.email} />
            {state.message && !state.error ? (
              <Alert tone="info" role="status">
                {state.message} Requested for <strong>{state.email}</strong>.
              </Alert>
            ) : null}
            {demoCode ? (
              <Alert tone="demo" title="Demo mode">
                Use the fixture-only code <strong className="font-mono tracking-widest">{demoCode}</strong>. It never works against the live mock services,
                which generate and deliver their own random code.
              </Alert>
            ) : state.delivery === "email" ? (
              <Alert tone="info" title="Check your inbox">
                The institution sends the code to the email registered on your account there. Check Spam if it has not arrived.
                The address above identifies the selected fictional banking customer.
              </Alert>
            ) : state.delivery === "server_log" ? (
              <Alert tone="info" title="Email delivery is not enabled">
                This instance currently sends codes to its development server log. Configure Gmail or another SMTP
                provider in the private <code className="font-mono">.env.mail</code> file to receive codes by email.
              </Alert>
            ) : null}
            <Field id="consent-code" label="Verification code" hint="Codes expire after 5 minutes and allow 5 attempts.">
              {(describedBy) => (
                <Input
                  id="consent-code"
                  name="code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  required
                  aria-describedby={describedBy}
                  aria-invalid={state.error ? true : undefined}
                  className="max-w-48 font-mono tracking-[0.3em]"
                />
              )}
            </Field>
            {state.error ? (
              <Alert tone="bad" role="alert" title="Verification failed">
                {state.error}
                {state.retryAfterSeconds ? ` Try again in ${state.retryAfterSeconds} seconds.` : ""}
              </Alert>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button type="submit" name="intent" value="verify" disabled={pending}>
                {pending ? "Verifying…" : "Verify and connect"}
              </Button>
              <Button type="submit" name="intent" value="request" variant="secondary" disabled={pending} formNoValidate>
                Send a new code
              </Button>
              <Button type="submit" name="intent" value="restart" variant="ghost" disabled={pending} formNoValidate>
                Use a different email
              </Button>
            </div>
          </>
        )}
      </form>
    </div>
  );
}

"use client";
import { useActionState } from "react";
import { signInAction } from "@/lib/actions/auth";
import { Alert, Button } from "@/components/ui/primitives";
import { Field, Input } from "@/components/ui/form";

export function EmailSignIn() {
  const [state,action,pending] = useActionState(signInAction,{step:"email",email:""});
  return <form action={action} className="space-y-5">
    {state.step === "email" ? <Field id="login-email" label="Your email address" hint="Use an inbox you control. We will email a one-time sign-in code.">
      {describedBy => <Input id="login-email" name="email" type="email" autoComplete="email" required defaultValue={state.email} aria-describedby={describedBy} />}
    </Field> : <>
      <input type="hidden" name="email" value={state.email}/>
      <p className="text-sm">Enter the code sent to <strong>{state.email}</strong>.</p>
      <Field id="login-code" label="Six-digit sign-in code" hint="Expires in 5 minutes. Five attempts maximum.">
        {describedBy => <Input id="login-code" name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required aria-describedby={describedBy}/>}
      </Field>
    </>}
    {state.message ? <Alert tone="info" role="status">{state.message}</Alert> : null}
    {state.error ? <Alert tone="bad" role="alert">{state.error}</Alert> : null}
    <div className="flex flex-wrap gap-2">
      <Button type="submit" name="intent" value={state.step === "email" ? "request" : "verify"} disabled={pending}>
        {pending ? "Please wait..." : state.step === "email" ? "Email my sign-in code" : "Verify and sign in"}
      </Button>
      {state.step === "code" ? <>
        <Button type="submit" name="intent" value="request" variant="secondary" disabled={pending} formNoValidate>Send a new code</Button>
        <Button type="submit" name="intent" value="restart" variant="ghost" disabled={pending} formNoValidate>Use another email</Button>
      </> : null}
    </div>
  </form>;
}

"use client";
import { useActionState } from "react";
import { refreshPlaidAction } from "@/lib/actions/plaid";
import { Alert, Button } from "@/components/ui/primitives";

export function PlaidRefresh() {
  const [state, action, pending] = useActionState(refreshPlaidAction, {});
  return <form action={action} className="space-y-3">
    <Button type="submit" variant="secondary" disabled={pending}>{pending ? "Refreshing bank data..." : "Refresh accounts and transactions"}</Button>
    {state.error ? <Alert tone="warn" role="alert">{state.error}</Alert> : state.message ? <Alert tone="info" role="status">{state.message}</Alert> : null}
  </form>;
}

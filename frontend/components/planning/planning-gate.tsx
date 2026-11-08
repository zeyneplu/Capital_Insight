import { Alert, ButtonLink, EmptyState } from "@/components/ui/primitives";
import type { PlanningLoad } from "@/lib/planning-server";

/** Shared non-ok states for Planning and Sam. Never substitutes fixture data for a failed live request. */
export function PlanningGate({ result, feature }: { result: Exclude<PlanningLoad<unknown>, { status: "ok" }>; feature: string }) {
  if (result.status === "unconfigured") {
    return (
      <EmptyState
        title={`${feature} needs the Capital Insight API`}
        description={
          <>
            Goals, forecasts and Sam are saved to your verified account, so they are not available with demo fixtures. Start the core backend, set{" "}
            <code>DATA_SOURCE=http</code> and <code>BACKEND_API_URL</code> in <code>frontend/.env.local</code>, then sign in.
          </>
        }
        action={<ButtonLink href="/">Back to Overview</ButtonLink>}
      />
    );
  }
  if (result.status === "signed-out") {
    return (
      <EmptyState
        title="Sign in to start planning"
        description={`${feature} uses the accounts linked to your verified email. Your goals and conversation stay private to you.`}
        action={<ButtonLink href="/sign-in">Sign in</ButtonLink>}
      />
    );
  }
  return (
    <Alert tone="bad" role="alert" title="Something went wrong">
      {result.message}
    </Alert>
  );
}

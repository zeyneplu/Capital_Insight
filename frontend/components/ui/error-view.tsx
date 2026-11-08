"use client";

import { useEffect } from "react";
import { Alert, Button, ButtonLink } from "./primitives";

/**
 * Shared error UI for error.tsx boundaries. In production, Next.js replaces
 * Server Component error messages with a generic one plus a `digest`, so we
 * show guidance and the digest instead of relying on `error.message`.
 * Demo data is never substituted for a failed request.
 */
export function ErrorView({ error, retry, title = "We couldn't load this page" }: { error: unknown; retry: () => void; title?: string }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  const digest = typeof error === "object" && error !== null && "digest" in error ? String((error as { digest?: unknown }).digest ?? "") : "";
  const devMessage = process.env.NODE_ENV !== "production" && error instanceof Error ? error.message : null;

  return (
    <div className="mx-auto max-w-xl space-y-4 py-8">
      <Alert tone="bad" role="alert" title={title}>
        <p>The data source did not respond as expected. Nothing was replaced with demo data.</p>
        <p className="mt-1">
          If you are running with <code className="font-mono">DATA_SOURCE=http</code>, the main backend is not available yet. Unset it (or set{" "}
          <code className="font-mono">DATA_SOURCE=mock</code>) to use demo data.
        </p>
        {devMessage ? <p className="mt-2 font-mono text-xs break-words">Development detail: {devMessage}</p> : null}
        {digest ? <p className="mt-2 font-mono text-xs">Reference: {digest}</p> : null}
      </Alert>
      <div className="flex gap-2">
        <Button type="button" onClick={() => retry()}>
          Try again
        </Button>
        <ButtonLink href="/" variant="secondary">
          Go to overview
        </ButtonLink>
      </div>
    </div>
  );
}

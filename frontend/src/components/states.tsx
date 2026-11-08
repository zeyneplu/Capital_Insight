/**
 * Loading, error and empty states. Every data view uses all three (see AGENTS.md):
 * a screen that silently shows nothing is the hardest bug to notice in a demo.
 */
import type { ApiError } from "@/lib/api";

export function Skeleton({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-3 ${className}`} role="status" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className="h-5 rounded bg-line/70 motion-safe:animate-pulse"
          style={{ width: `${92 - i * 14}%` }}
        />
      ))}
    </div>
  );
}

export function ErrorNotice({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-poor/40 bg-surface p-4">
      <p className="text-ink">{error.message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 rounded-md border border-line px-3 py-1.5 text-sm font-medium text-ink hover:border-accent"
      >
        Try again
      </button>
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-ink-3">{children}</p>;
}

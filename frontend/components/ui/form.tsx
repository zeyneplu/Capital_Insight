import type { ComponentProps, ReactNode } from "react";
import { cx } from "./primitives";

/**
 * Accessible field wrapper: the label is bound to the control, and hint/error
 * text is announced through aria-describedby. Hook-free, so it works in both
 * Server and Client Components.
 */
export function Field({
  id,
  label,
  hint,
  error,
  children,
  className,
}: {
  id: string;
  label: ReactNode;
  hint?: ReactNode;
  error?: string;
  children: (describedBy: string | undefined, invalid: boolean) => ReactNode;
  className?: string;
}) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {children(describedBy, Boolean(error))}
      {hint ? (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-xs font-medium text-bad">
          <span aria-hidden="true">✕ </span>
          {error}
        </p>
      ) : null}
    </div>
  );
}

const CONTROL =
  "min-h-10 w-full rounded-lg border bg-surface px-3 text-sm text-text placeholder:text-muted/70 disabled:opacity-60 aria-[invalid=true]:border-bad";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input {...props} className={cx(CONTROL, "border-border-strong", className)} />;
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return <select {...props} className={cx(CONTROL, "border-border-strong pr-8", className)} />;
}

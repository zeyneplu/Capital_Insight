import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

/** Joins class names, skipping falsy values. */
export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

// ---------------------------------------------------------------------------
// Layout
// ---------------------------------------------------------------------------

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {description ? <div className="mt-1 max-w-2xl text-sm text-muted">{description}</div> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}

export function Card({
  title,
  description,
  action,
  children,
  className,
  as: Tag = "section",
  headingLevel = 2,
}: {
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  as?: "section" | "article" | "div";
  headingLevel?: 2 | 3;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  return (
    <Tag className={cx("rounded-xl border border-border bg-surface p-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)] sm:p-5", className)}>
      {title || action ? (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            {title ? <Heading className="text-base font-semibold">{title}</Heading> : null}
            {description ? <p className="mt-0.5 text-sm text-muted">{description}</p> : null}
          </div>
          {action}
        </div>
      ) : null}
      {children}
    </Tag>
  );
}

export function StatTile({ label, value, hint, tone = "neutral" }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "neutral" | "good" | "bad" }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 sm:p-5">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className={cx("mt-1 text-2xl font-semibold tabular-nums tracking-tight", tone === "good" && "text-good", tone === "bad" && "text-bad")}>
        {value}
      </dd>
      {hint ? <dd className="mt-1 text-xs text-muted">{hint}</dd> : null}
    </div>
  );
}

/** A label/value list for record details. Rows with null values are skipped by callers. */
export function DetailList({ items }: { items: Array<{ label: string; value: ReactNode } | null | false> }) {
  const rows = items.filter((item): item is { label: string; value: ReactNode } => Boolean(item));
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
      {rows.map((row) => (
        <div key={row.label} className="flex justify-between gap-4 border-b border-border pb-2 sm:block sm:border-0 sm:pb-0">
          <dt className="text-sm text-muted">{row.label}</dt>
          <dd className="text-right text-sm font-medium tabular-nums sm:mt-0.5 sm:text-left">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

// ---------------------------------------------------------------------------
// Status and feedback
// ---------------------------------------------------------------------------

export type Tone = "neutral" | "info" | "good" | "warn" | "bad" | "demo";

const BADGE_TONES: Record<Tone, string> = {
  neutral: "bg-surface-muted text-muted",
  info: "bg-primary-soft text-primary",
  good: "bg-good-soft text-good",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  demo: "bg-demo-soft text-demo",
};

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", BADGE_TONES[tone], className)}>
      {children}
    </span>
  );
}

/** Status pairs color with an icon and text, so meaning never relies on color alone. */
export function StatusBadge({ status }: { status: "approved" | "declined" }) {
  return status === "approved" ? (
    <Badge tone="good">
      <span aria-hidden="true">✓</span> Approved
    </Badge>
  ) : (
    <Badge tone="bad">
      <span aria-hidden="true">✕</span> Declined
    </Badge>
  );
}

export function DemoBadge({ children = "Demo data" }: { children?: ReactNode }) {
  return (
    <Badge tone="demo">
      <span aria-hidden="true">◆</span> {children}
    </Badge>
  );
}

const ALERT_TONES: Record<Exclude<Tone, "neutral">, { box: string; icon: string }> = {
  info: { box: "border-primary/30 bg-primary-soft", icon: "ℹ" },
  good: { box: "border-good/30 bg-good-soft", icon: "✓" },
  warn: { box: "border-warn/30 bg-warn-soft", icon: "!" },
  bad: { box: "border-bad/30 bg-bad-soft", icon: "✕" },
  demo: { box: "border-demo/30 bg-demo-soft", icon: "◆" },
};

export function Alert({
  tone = "info",
  title,
  children,
  role,
  className,
}: {
  tone?: Exclude<Tone, "neutral">;
  title?: ReactNode;
  children?: ReactNode;
  /** Use "alert" for errors the user must notice now, "status" for polite updates. */
  role?: "alert" | "status";
  className?: string;
}) {
  const style = ALERT_TONES[tone];
  return (
    <div role={role} className={cx("flex gap-3 rounded-lg border p-3 text-sm", style.box, className)}>
      <span aria-hidden="true" className="mt-0.5 font-bold">
        {style.icon}
      </span>
      <div className="min-w-0 space-y-1">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className="text-text/90">{children}</div> : null}
      </div>
    </div>
  );
}

export function EmptyState({ title, description, action }: { title: string; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-dashed border-border-strong px-4 py-10 text-center">
      <p className="font-medium">{title}</p>
      {description ? <p className="mt-1 max-w-md text-sm text-muted">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx("animate-pulse rounded-md bg-surface-muted", className)} />;
}

/** A labeled loading region: screen readers hear the label, sighted users see the skeleton. */
export function LoadingBlock({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

export function Meter({ value, label, tone = "info" }: { value: number; label: string; tone?: "info" | "warn" | "bad" }) {
  const clamped = Math.min(Math.max(value, 0), 1);
  const fill = tone === "bad" ? "bg-bad" : tone === "warn" ? "bg-warn" : "bg-series-1";
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped * 100)}
      className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted"
    >
      <div className={cx("h-full rounded-full", fill)} style={{ width: `${clamped * 100}%` }} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Buttons and links
// ---------------------------------------------------------------------------

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-contrast hover:bg-primary-hover",
  secondary: "border border-border-strong bg-surface text-text hover:bg-surface-muted",
  ghost: "text-primary hover:bg-primary-soft",
  danger: "border border-bad/40 bg-surface text-bad hover:bg-bad-soft",
};

export function buttonClass(variant: ButtonVariant = "primary", size: "sm" | "md" = "md"): string {
  return cx(
    "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
    size === "sm" ? "min-h-9 px-3 text-sm" : "min-h-10 px-4 text-sm",
    BUTTON_VARIANTS[variant],
  );
}

export function Button({ variant = "primary", size = "md", className, ...props }: ComponentProps<"button"> & { variant?: ButtonVariant; size?: "sm" | "md" }) {
  return <button {...props} className={cx(buttonClass(variant, size), className)} />;
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ComponentProps<typeof Link> & { variant?: ButtonVariant; size?: "sm" | "md" }) {
  return <Link {...props} className={cx(buttonClass(variant, size), className)} />;
}

export function TextLink({ className, ...props }: ComponentProps<typeof Link>) {
  return <Link {...props} className={cx("font-medium text-primary underline-offset-4 hover:underline", className)} />;
}

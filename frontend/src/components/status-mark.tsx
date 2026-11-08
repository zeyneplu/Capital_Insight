import type { Schemas } from "@/lib/api";

type Status = Schemas["Status"];

// Color is never the only signal: each status has its own shape and a text label.
const LABELS: Record<Status, string> = {
  good: "Good",
  fair: "Fair",
  poor: "Needs attention",
  unknown: "Not enough data",
};

function StatusIcon({ status }: { status: Status }) {
  const common = { width: 16, height: 16, viewBox: "0 0 16 16", "aria-hidden": true } as const;
  switch (status) {
    case "good": // circle + check
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="7.5" fill="var(--status-good)" />
          <path d="M4.8 8.3l2.1 2.1 4.3-4.6" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "fair": // triangle + bar
      return (
        <svg {...common}>
          <path d="M8 1.2l7 13H1z" fill="var(--status-fair)" />
          <path d="M8 6v3.6" stroke="#12362b" strokeWidth="1.8" strokeLinecap="round" />
          <circle cx="8" cy="11.9" r="1" fill="#12362b" />
        </svg>
      );
    case "poor": // square + exclamation
      return (
        <svg {...common}>
          <rect x="1" y="1" width="14" height="14" rx="3" fill="var(--status-poor)" />
          <path d="M8 4.3v4.6" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" />
          <circle cx="8" cy="11.6" r="1.05" fill="#fff" />
        </svg>
      );
    default: // dashed ring: nothing to judge yet
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="6.5" fill="none" stroke="var(--status-unknown)" strokeWidth="1.6" strokeDasharray="2.6 2" />
        </svg>
      );
  }
}

export function StatusMark({ status }: { status: Status }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-ink-2">
      <StatusIcon status={status} />
      {LABELS[status]}
    </span>
  );
}

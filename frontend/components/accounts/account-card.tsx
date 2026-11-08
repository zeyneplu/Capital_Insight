import Link from "next/link";
import { Money } from "@/components/ui/money";
import { Badge, Meter } from "@/components/ui/primitives";
import { ratioForDisplay, toCents } from "@/lib/finance/money";
import { ACCOUNT_TYPE_LABELS, formatDate, formatRate, formatRatio } from "@/lib/format";
import type { Account } from "@/lib/types";

/** Utilization above 30% is a common rule of thumb for when card balances start to weigh on credit. */
export function utilizationOf(account: Account): number | null {
  if (account.type !== "credit_card" || !account.details.creditLimit) return null;
  return ratioForDisplay(toCents(account.balance), toCents(account.details.creditLimit));
}

function Highlight({ account }: { account: Account }) {
  const { details } = account;
  const utilization = utilizationOf(account);
  if (utilization !== null) {
    return (
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs text-muted">
          <span>{formatRatio(utilization, { whole: true })} of limit used</span>
          {details.purchaseApr ? <span>{formatRate(details.purchaseApr)} APR</span> : null}
        </div>
        <Meter value={utilization} label="Credit used" tone={utilization > 0.3 ? "warn" : "info"} />
      </div>
    );
  }
  if (details.originalPrincipal) {
    const paid = ratioForDisplay(toCents(details.originalPrincipal) - toCents(account.balance), toCents(details.originalPrincipal));
    return (
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs text-muted">
          <span>{formatRatio(paid, { whole: true })} of principal repaid</span>
          {details.apr ? <span>{formatRate(details.apr)} APR</span> : null}
        </div>
        <Meter value={paid} label="Principal repaid" />
      </div>
    );
  }
  const facts = [
    details.apy ? `${formatRate(details.apy)} APY` : null,
    details.maturityDate ? `Matures ${formatDate(details.maturityDate)}` : null,
    details.subtype ? `${details.subtype[0].toUpperCase()}${details.subtype.slice(1)} ${ACCOUNT_TYPE_LABELS[account.type]}` : null,
  ].filter(Boolean);
  return facts.length ? <p className="text-xs text-muted">{facts.join(" · ")}</p> : null;
}

export function AccountCard({ account }: { account: Account }) {
  const owed = account.classification === "liability";
  return (
    <article className="relative flex h-full flex-col gap-4 rounded-xl border border-border bg-surface p-4 transition-colors focus-within:border-primary hover:border-border-strong">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold">
            <Link href={`/accounts/${encodeURIComponent(account.id)}`} className="after:absolute after:inset-0 after:content-['']">
              {account.name}
            </Link>
          </h3>
          <p className="text-xs text-muted">•••• {account.last4}</p>
        </div>
        <Badge tone={owed ? "warn" : "info"}>{ACCOUNT_TYPE_LABELS[account.type]}</Badge>
      </div>
      <div>
        <p className="text-xs text-muted">{owed ? "Amount owed" : "Balance"}</p>
        <Money value={account.balance} className="text-xl font-semibold tracking-tight" />
      </div>
      <div className="mt-auto">
        <Highlight account={account} />
      </div>
    </article>
  );
}

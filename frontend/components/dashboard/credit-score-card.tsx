import { Badge, Card } from "@/components/ui/primitives";
import { formatDate } from "@/lib/format";
import { creditScoreLabel } from "@/lib/data/credit-score";
import type { CreditScoreSummary } from "@/lib/types";

export function CreditScoreCard({credit}: {credit:CreditScoreSummary}) {
  if (credit.status === "connect_bank") return null;
  if (credit.score === null) return <Card title="Your credit score"><p className="text-sm text-muted">{credit.status === "conflicting_profiles" ? "Connected mock customer profiles report different scores. Link the same customer identity at each institution to see one consistent score." : "Your connected bank could not provide a credit score. Try again later."}</p></Card>;
  const position = Math.max(0,Math.min(100,(credit.score-credit.minimum)/(credit.maximum-credit.minimum)*100));
  return <Card>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="font-semibold">Your credit score</h2><p className="mt-1 text-xs text-muted">One profile across your connected mock banks</p></div>
      <Badge tone="demo">Synthetic demo</Badge>
    </div>
    <div className="my-5 flex items-baseline gap-3"><strong className="text-5xl font-semibold tabular-nums tracking-tight">{credit.score}</strong><span className="text-sm font-medium">{creditScoreLabel(credit.score)}</span></div>
    <div role="meter" aria-label="Synthetic credit score" aria-valuemin={credit.minimum} aria-valuemax={credit.maximum} aria-valuenow={credit.score} aria-valuetext={`${credit.score}, ${creditScoreLabel(credit.score)}`} className="relative py-2">
      <div className="h-2.5 rounded-full bg-gradient-to-r from-red-400 via-amber-300 to-emerald-400" />
      <span aria-hidden="true" className="absolute top-0 h-6 w-1 -translate-x-1/2 rounded bg-text ring-2 ring-surface" style={{left:`${position}%`}} />
    </div>
    <div className="flex justify-between text-xs text-muted"><span>{credit.minimum}</span><span>{credit.maximum}</span></div>
    <p className="mt-4 text-xs text-muted">{credit.model}{credit.as_of ? ` · Updated ${formatDate(credit.as_of)}` : ""}</p>
    <p className="mt-1 text-xs text-muted">Provided by {credit.sources.join(", ")}. This is fictional test data, not a bureau report or a lending decision.</p>
  </Card>;
}

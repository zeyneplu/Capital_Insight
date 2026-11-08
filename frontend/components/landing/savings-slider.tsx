"use client";
import { useId, useState } from "react";
import { formatMoney } from "@/lib/format";

const GOALS = [
  { id: "college", label: "College", color: "#a78bfa", target: 20000 },
  { id: "car", label: "A car", color: "#38bdf8", target: 12000 },
  { id: "cushion", label: "Emergency fund", color: "#fb7185", target: 10000 },
  { id: "retire", label: "Retirement", color: "#34d399", target: 100000 },
] as const;

/** Integer-cent projection: month-end deposits, monthly compounding, rounded to cents each month. */
function project(monthly: number, months: number, annualPct: number): bigint[] {
  const deposit = BigInt(monthly * 100);
  const rateBps = BigInt(Math.round(annualPct * 100)); // basis points per year
  const points: bigint[] = [0n];
  let balance = 0n;
  for (let month = 1; month <= months; month++) {
    const interest = (balance * rateBps + 60000n) / 120000n; // balance × bps / (12 × 10000), rounded
    balance += interest + deposit;
    points.push(balance);
  }
  return points;
}

const dollars = (cents: bigint) => formatMoney(`${cents / 100n}.${String(cents % 100n).padStart(2, "0")}`, { whole: true });

export function SavingsSlider() {
  const id = useId();
  const [goal, setGoal] = useState<(typeof GOALS)[number]>(GOALS[0]);
  const [monthly, setMonthly] = useState(350);
  const [months, setMonths] = useState(36);
  const [rate, setRate] = useState(3);
  const points = project(monthly, months, rate);
  const final = points[points.length - 1];
  const target = BigInt(goal.target * 100);
  const progress = Number((final * 1000n) / target) / 10;
  const max = Number(points[points.length - 1]) || 1;
  const path = points
    .map((value, index) => `${(index / months) * 300},${110 - (Number(value) / Math.max(max, Number(target))) * 100}`)
    .join(" L");
  const targetY = 110 - (Number(target) / Math.max(max, Number(target))) * 100;

  return (
    <div className="rounded-3xl border border-border bg-surface p-5 shadow-xl shadow-black/5 sm:p-7">
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Pick a goal">
        {GOALS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="radio"
            aria-checked={goal.id === item.id}
            onClick={() => setGoal(item)}
            className="rounded-full border px-3.5 py-1.5 text-sm font-semibold transition hover:-translate-y-0.5"
            style={goal.id === item.id ? { background: item.color, borderColor: item.color, color: "#0b1020" } : { borderColor: item.color + "66", color: item.color }}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <div className="space-y-5">
          {[
            { key: "monthly", label: "Monthly savings", value: monthly, set: setMonthly, min: 25, max: 2000, step: 25, shown: formatMoney(String(monthly), { whole: true }) },
            { key: "months", label: "Timeline", value: months, set: setMonths, min: 6, max: 120, step: 6, shown: `${months} months` },
            { key: "rate", label: "Assumed yearly return", value: rate, set: setRate, min: 0, max: 8, step: 0.5, shown: `${rate}%` },
          ].map((slider) => (
            <div key={slider.key}>
              <div className="flex items-baseline justify-between text-sm">
                <label htmlFor={`${id}-${slider.key}`} className="text-muted">{slider.label}</label>
                <strong className="tabular-nums" style={{ color: goal.color }}>{slider.shown}</strong>
              </div>
              <input
                id={`${id}-${slider.key}`}
                type="range"
                min={slider.min}
                max={slider.max}
                step={slider.step}
                value={slider.value}
                onChange={(event) => slider.set(Number(event.target.value))}
                className="mt-2 w-full"
                style={{ accentColor: goal.color }}
              />
            </div>
          ))}
          <p className="text-xs text-muted">Illustration only. Returns are an adjustable assumption, not a prediction; excludes taxes, fees and inflation.</p>
        </div>

        <div className="rounded-2xl bg-slate-950 p-5 text-white">
          <p className="text-xs uppercase tracking-widest text-slate-400">In {months} months you could have</p>
          <p className="mt-1 text-4xl font-semibold tabular-nums" aria-live="polite">{dollars(final)}</p>
          <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-white/10" role="progressbar" aria-label={`${goal.label} target progress`} aria-valuenow={Math.min(100, Math.round(progress))} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${Math.min(100, progress)}%`, background: goal.color }} />
          </div>
          <p className="mt-2 text-sm text-slate-300">
            {progress >= 100 ? (
              <>Goal reached: <strong style={{ color: goal.color }}>{dollars(target)}</strong> {goal.label.toLowerCase()} target 🎉</>
            ) : (
              <>{Math.round(progress)}% of a {dollars(target)} {goal.label.toLowerCase()} target</>
            )}
          </p>
          <svg viewBox="0 0 300 115" className="mt-4 w-full" role="img" aria-label={`Savings grow to ${dollars(final)} over ${months} months`}>
            <line x1="0" x2="300" y1={targetY} y2={targetY} stroke="white" strokeOpacity="0.25" strokeDasharray="4 4" />
            <text x="296" y={targetY - 4} textAnchor="end" fontSize="9" fill="white" fillOpacity="0.55">target</text>
            <path d={`M0,110 L${path} L300,110 Z`} fill={goal.color} fillOpacity="0.15" />
            <path d={`M${path}`} fill="none" stroke={goal.color} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
          </svg>
        </div>
      </div>
    </div>
  );
}

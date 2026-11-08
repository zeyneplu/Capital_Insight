/**
 * Turns the backend's health indicators into plain-English sentences, and picks the
 * one that matters most for the top of the dashboard. Wording only: every number
 * comes from the backend and is just formatted here.
 */
import type { Schemas } from "./api";
import { formatIndicator, formatMoney, formatPercent } from "./format";

type Indicator = Schemas["Indicator"];
type Status = Indicator["status"];

export type Insight = {
  key: string;
  status: Status;
  headline: string;
  advice: string;
};

// Worst first; among equals, the order people care about most.
const SEVERITY: Record<Status, number> = { poor: 0, fair: 1, good: 2, unknown: 3 };
const PRIORITY = [
  "credit_utilization",
  "debt_payoff_savings",
  "emergency_fund_months",
  "savings_rate",
];

const ADVICE: Record<string, Partial<Record<Status, string>>> = {
  credit_utilization: {
    good: "That's a healthy level for your credit score.",
    fair: "Getting under 10% is where credit scores do best.",
    poor: "Above 30% pulls credit scores down. Paying it down is the fastest fix.",
  },
  debt_payoff_savings: {
    fair: "Use cash beyond your 3-month safety net to pay down your highest-interest debt.",
  },
  emergency_fund_months: {
    good: "That's a solid safety net.",
    fair: "Six months of expenses is a comfortable cushion.",
    poor: "Building toward 3 months protects you from surprise bills.",
  },
  savings_rate: {
    good: "That's a strong habit.",
    fair: "Keeping 20% or more builds savings fastest.",
    poor: "Starting with 10% of each paycheck makes a real difference.",
  },
};

export function toInsight(indicator: Indicator): Insight | null {
  const { key, status, value } = indicator;
  if (value === null || status === "unknown") return null;

  let headline: string;
  switch (key) {
    case "credit_utilization":
      headline = `Your cards are using ${formatPercent(value)} of their limits.`;
      break;
    case "debt_payoff_savings":
      if (status === "good") return null; // nothing to stop paying: no sentence needed
      headline = `You could stop paying ${formatMoney(value)} a year in interest.`;
      break;
    case "emergency_fund_months":
      headline = `Your cash covers ${formatIndicator(indicator)} of expenses.`;
      break;
    case "savings_rate":
      headline = `You keep ${formatPercent(value)} of what you earn.`;
      break;
    default:
      return null; // an indicator we have no wording for yet
  }
  return { key, status, headline, advice: ADVICE[key]?.[status] ?? "" };
}

export function rankInsights(report: Schemas["HealthReport"]): Insight[] {
  const rank = (key: string) => {
    const i = PRIORITY.indexOf(key);
    return i === -1 ? PRIORITY.length : i;
  };
  return report.indicators
    .map(toInsight)
    .filter((insight): insight is Insight => insight !== null)
    .sort((a, b) => SEVERITY[a.status] - SEVERITY[b.status] || rank(a.key) - rank(b.key));
}

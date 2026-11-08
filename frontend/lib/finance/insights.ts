/**
 * Rule-based SAMPLE insights computed from the demo portfolio.
 *
 * These are placeholders for the future NVIDIA Nemotron analysis that the
 * main backend will provide. They are fixed, transparent rules (not AI) and
 * not financial advice. Each insight shows the numbers it was computed from.
 */
import type { Account, Dashboard, InsightReport, Insight } from "../types.ts";
import { fromCents, ratioForDisplay, toCents } from "./money.ts";

const pct = (value: number) => `${Math.round(value * 100)}%`;
const usd = (cents: bigint) => fromCents(cents);

export function buildSampleInsights(dashboard: Dashboard, accounts: readonly Account[]): InsightReport {
  const items: Insight[] = [];
  const fullMonths = dashboard.cashFlow.filter((month) => !month.partial);

  // 1. Credit utilization across all cards
  const cards = accounts.filter((account) => account.type === "credit_card" && account.details.creditLimit);
  if (cards.length) {
    const balance = cards.reduce((sum, card) => sum + toCents(card.balance), 0n);
    const limit = cards.reduce((sum, card) => sum + toCents(card.details.creditLimit!), 0n);
    const utilization = ratioForDisplay(balance, limit);
    items.push({
      id: "credit-utilization",
      title: utilization < 0.1 ? "Card balances are low relative to your limits" : utilization < 0.3 ? "Card utilization is moderate" : "Card utilization is high",
      body: `You are using ${pct(utilization)} of ${fromCentsLabel(limit)} in combined credit limits across ${cards.length} cards. A common rule of thumb is to stay under 30%.`,
      tone: utilization < 0.3 ? "good" : "warn",
      metric: { label: "Utilization", value: pct(utilization) },
      basis: [`Card balances ${usd(balance)}`, `Credit limits ${usd(limit)}`],
    });
  }

  // 2. Emergency fund coverage
  const liquid = accounts.filter((account) => account.type === "checking" || account.type === "savings").reduce((sum, account) => sum + toCents(account.balance), 0n);
  if (fullMonths.length && liquid > 0n) {
    const averageSpending = fullMonths.reduce((sum, month) => sum + toCents(month.spending), 0n) / BigInt(fullMonths.length);
    if (averageSpending > 0n) {
      const months = Number((liquid * 10n) / averageSpending) / 10;
      items.push({
        id: "emergency-fund",
        title: months >= 6 ? "Your cash covers six months or more of spending" : months >= 3 ? "Your cash covers a few months of spending" : "Your cash cushion is thin",
        body: `Checking and savings hold ${fromCentsLabel(liquid)}, about ${months.toFixed(1)} months of your average everyday spending (${fromCentsLabel(averageSpending)} per full month). Many guides suggest three to six months.`,
        tone: months >= 3 ? "good" : "warn",
        metric: { label: "Months covered", value: months.toFixed(1) },
        basis: [`Liquid balances ${usd(liquid)}`, `Average monthly spending ${usd(averageSpending)} over ${fullMonths.length} full months`],
      });
    }
  }

  // 3. Biggest spending category
  const top = dashboard.spending.byCategory[0];
  if (top && toCents(dashboard.spending.total) > 0n) {
    const share = ratioForDisplay(toCents(top.amount), toCents(dashboard.spending.total));
    items.push({
      id: "top-category",
      title: `${capitalize(top.category.replace("_", " "))} is your largest spending category`,
      body: `${fromCentsLabel(toCents(top.amount))} across ${top.count} transactions, ${pct(share)} of the last 30 days of spending.`,
      tone: "info",
      metric: { label: "Share of spending", value: pct(share) },
      basis: [`Window ${dashboard.spending.windowStart} to ${dashboard.spending.windowEnd}`, "Transfers, paychecks and debt payments excluded"],
    });
  }

  // 4. Fixed debt payments versus income
  if (fullMonths.length) {
    const averageIncome = fullMonths.reduce((sum, month) => sum + toCents(month.income), 0n) / BigInt(fullMonths.length);
    const monthlyDebt = dashboard.obligations.reduce((sum, obligation) => sum + toCents(obligation.amount), 0n);
    if (averageIncome > 0n) {
      const ratio = ratioForDisplay(monthlyDebt, averageIncome);
      items.push({
        id: "debt-to-income",
        title: ratio <= 0.36 ? "Debt payments are within a common guideline" : "Debt payments take a large share of income",
        body: `Scheduled debt payments of about ${fromCentsLabel(monthlyDebt)} a month are ${pct(ratio)} of average take-home deposits (${fromCentsLabel(averageIncome)}). Lenders often look for 36% or less.`,
        tone: ratio <= 0.36 ? "good" : "warn",
        metric: { label: "Debt-to-income", value: pct(ratio) },
        basis: [`Upcoming obligations ${usd(monthlyDebt)}`, `Average paycheck deposits ${usd(averageIncome)}`],
      });
    }
  }

  // 5. Highest-rate debt
  const rated = accounts
    .filter((account) => account.classification === "liability" && toCents(account.balance) > 0n)
    .map((account) => ({ account, rate: account.details.purchaseApr ?? account.details.apr }))
    .filter((entry): entry is { account: Account; rate: string } => entry.rate !== null)
    .sort((a, b) => Number(toBasisPoints(b.rate) - toBasisPoints(a.rate)));
  if (rated.length) {
    const { account, rate } = rated[0];
    items.push({
      id: "highest-rate",
      title: `${account.name} has your highest interest rate`,
      body: `At ${(Number(toBasisPoints(rate)) / 100).toFixed(2)}% APR on ${fromCentsLabel(toCents(account.balance))}, extra payments here reduce interest the most (the "avalanche" approach).`,
      tone: "info",
      metric: { label: "APR", value: `${(Number(toBasisPoints(rate)) / 100).toFixed(2)}%` },
      basis: [`Compared ${rated.length} balances that report a rate`],
    });
  }

  return { source: "sample-rules", snapshotDate: dashboard.snapshotDate, items };
}

function toBasisPoints(rate: string): bigint {
  // "0.2299" -> 2299 basis points, exactly.
  const [whole, fraction = ""] = rate.split(".");
  return BigInt(whole) * 10_000n + BigInt((fraction + "0000").slice(0, 4));
}

function capitalize(text: string) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function fromCentsLabel(cents: bigint): string {
  const value = fromCents(cents);
  const [whole, fraction] = value.split(".");
  return `$${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${fraction}`;
}

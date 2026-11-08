/**
 * Display formatting only. The backend sends money as exact decimal strings ("600.00").
 * We convert to Number ONLY to format text for the screen: never add, subtract, or
 * compare money here. All math happens in the backend engine.
 */
import type { Schemas } from "./api";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const usdWhole = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const percent = new Intl.NumberFormat("en-US", { style: "percent", maximumFractionDigits: 1 });
const oneDecimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const shortDate = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});

export const formatMoney = (value: string) => usd.format(Number(value));
export const formatMoneyWhole = (value: string) => usdWhole.format(Number(value));
export const formatPercent = (ratio: string) => percent.format(Number(ratio));
export const formatDate = (isoDate: string) => shortDate.format(new Date(isoDate));

export function formatIndicator(indicator: Schemas["Indicator"]): string {
  if (indicator.value === null) return "Not enough data";
  switch (indicator.unit) {
    case "ratio":
      return formatPercent(indicator.value);
    case "months":
      return `${oneDecimal.format(Number(indicator.value))} months`;
    case "usd_per_year":
      return `${formatMoney(indicator.value)} a year`;
    default:
      return indicator.value;
  }
}

const ACCOUNT_TYPES: Record<Schemas["AccountType"], string> = {
  checking: "Checking",
  savings: "Savings",
  cash: "Cash",
  cd: "CD",
  ira: "IRA",
  credit_card: "Credit card",
  loan: "Loan",
  mortgage: "Mortgage",
};

export const accountTypeLabel = (type: Schemas["AccountType"]) => ACCOUNT_TYPES[type];

export const categoryLabel = (category: string) =>
  category.charAt(0).toUpperCase() + category.slice(1);

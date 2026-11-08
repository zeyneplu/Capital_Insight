import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { rankInsights, toInsight } from "./insights";

type Indicator = Schemas["Indicator"];

const indicator = (overrides: Partial<Indicator>): Indicator => ({
  key: "credit_utilization",
  label: "Credit utilization",
  value: "0.2400",
  unit: "ratio",
  status: "fair",
  detail: "",
  ...overrides,
});

// The exact health report the backend returns for the demo-alex persona.
const ALEX: Schemas["HealthReport"] = {
  customer_id: "demo-alex",
  indicators: [
    indicator({}),
    indicator({ key: "emergency_fund_months", value: "4.4667", unit: "months", status: "fair" }),
    indicator({ key: "savings_rate", value: "0.5313", unit: "ratio", status: "good" }),
    indicator({ key: "debt_payoff_savings", value: "78.00", unit: "usd_per_year", status: "fair" }),
  ],
};

describe("toInsight", () => {
  it("writes a sentence with the backend's number, formatted", () => {
    expect(toInsight(indicator({}))?.headline).toBe("Your cards are using 24% of their limits.");
  });

  it("formats money and months", () => {
    expect(
      toInsight(indicator({ key: "debt_payoff_savings", value: "78.00", unit: "usd_per_year" }))
        ?.headline,
    ).toBe("You could stop paying $78.00 a year in interest.");
    expect(
      toInsight(indicator({ key: "emergency_fund_months", value: "4.4667", unit: "months" }))
        ?.headline,
    ).toBe("Your cash covers 4.5 months of expenses.");
  });

  it("says nothing when there is no data, instead of guessing", () => {
    expect(toInsight(indicator({ value: null, status: "unknown" }))).toBeNull();
  });

  it("skips 'interest you could stop paying' when it is zero", () => {
    expect(
      toInsight(indicator({ key: "debt_payoff_savings", value: "0.00", status: "good" })),
    ).toBeNull();
  });
});

describe("rankInsights", () => {
  it("puts the most important problem first", () => {
    expect(rankInsights(ALEX).map((i) => i.key)).toEqual([
      "credit_utilization", // fair, highest priority
      "debt_payoff_savings", // fair
      "emergency_fund_months", // fair
      "savings_rate", // good comes last
    ]);
  });

  it("ranks a poor indicator above any fair one", () => {
    const report = {
      ...ALEX,
      indicators: [...ALEX.indicators, indicator({ key: "savings_rate", status: "poor" })],
    };
    expect(rankInsights(report)[0]).toMatchObject({ key: "savings_rate", status: "poor" });
  });
});

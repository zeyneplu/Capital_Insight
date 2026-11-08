/**
 * Synthetic institutions, mirroring the configured mock services
 * (services/mock_bank compose instances, mock_loan, mock_mortgage).
 * Names follow the services' BANK_NAME / LENDER_NAME defaults. No real
 * logos, branding, customers or account numbers are used.
 */
import type { ConnectableInstitution, IsoDate, RawCustomer } from "../../types.ts";

/** Fixed fixture snapshot. Matches the services' default SEED_DATE. */
export const SNAPSHOT_DATE: IsoDate = "2026-11-01";
export const SNAPSHOT_TIMESTAMP = `${SNAPSHOT_DATE}T00:00:00Z`;

/**
 * Fixture-only consent code. Live services generate a random six-digit code
 * and print it only in their DEMO_MODE server logs; this code never works there.
 */
export const DEMO_CONSENT_CODE = "424242";

export const INSTITUTIONS: readonly ConnectableInstitution[] = [
  {
    id: "chase",
    name: "Chase Mock Bank",
    shortName: "Chase (mock)",
    service: "mock_bank",
    description: "Checking, savings and a credit card.",
    products: ["checking", "savings", "credit_card"],
    demoEmail: "customer1@chase.example.test",
    defaultPort: 8001,
  },
  {
    id: "amex",
    name: "American Express Mock Bank",
    shortName: "Amex (mock)",
    service: "mock_bank",
    description: "A credit card and a high-yield savings account.",
    products: ["credit_card", "savings"],
    demoEmail: "customer1@amex.example.test",
    defaultPort: 8002,
  },
  {
    id: "pnc",
    name: "PNC Mock Bank",
    shortName: "PNC (mock)",
    service: "mock_bank",
    description: "Deposits, CDs, a Roth IRA and an auto loan.",
    products: ["checking", "savings", "cd", "personal_loan", "auto_loan", "mortgage", "ira"],
    demoEmail: "customer1@pnc.example.test",
    defaultPort: 8003,
  },
  {
    id: "discover",
    name: "Discover Mock Bank",
    shortName: "Discover (mock)",
    service: "mock_bank",
    description: "A credit card, a personal loan and savings.",
    products: ["credit_card", "personal_loan", "savings"],
    demoEmail: "customer1@discover.example.test",
    defaultPort: 8004,
  },
  {
    id: "loans",
    name: "Capital Insight Mock Loans",
    shortName: "Mock Loans",
    service: "mock_loan",
    description: "Simulated personal, auto and mortgage loan applications.",
    products: ["personal_loan", "auto_loan", "mortgage"],
    demoEmail: "customer1@loans.example.test",
    defaultPort: 8005,
  },
  {
    id: "mortgages",
    name: "Capital Insight Mock Mortgages",
    shortName: "Mock Mortgages",
    service: "mock_mortgage",
    description: "Simulated fixed-rate mortgage applications.",
    products: ["mortgage"],
    demoEmail: "customer1@mortgages.example.test",
    defaultPort: 8006,
  },
];

/**
 * Connected when the demo starts. Discover is left unconnected on purpose so
 * the connection flow visibly changes the dashboard.
 */
export const DEFAULT_CONNECTIONS: readonly string[] = ["chase", "amex", "pnc", "loans", "mortgages"];

export function findInstitution(id: string): ConnectableInstitution | undefined {
  return INSTITUTIONS.find((institution) => institution.id === id);
}

/**
 * Each service has its own synthetic customer and token scope. The app links
 * these connections because the user consented to each in one session, not
 * because names or emails happen to match.
 */
export function customerFor(institutionId: string): RawCustomer {
  return {
    id: `${institutionId}-customer-001`,
    first_name: "Jordan",
    last_name: "Rivera",
    email: `customer1@${institutionId}.example.test`,
    date_of_birth: "1990-03-12",
    synthetic_identity_id: `SYNTH-${institutionId}-customer-001`,
    created_at: SNAPSHOT_TIMESTAMP,
  };
}

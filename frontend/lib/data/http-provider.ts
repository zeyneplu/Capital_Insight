import "server-only";
import type { DataProvider } from "./provider";
import { DataSourceUnavailableError } from "./provider";

/**
 * Placeholder for the future Capital Insight main backend (FastAPI).
 *
 * The main backend does not exist yet and has no agreed API contract, so this
 * provider deliberately fails loudly instead of guessing endpoints or quietly
 * serving fixtures. When the backend lands:
 *  1. Read BACKEND_API_URL here (server-only; never NEXT_PUBLIC_).
 *  2. Fetch with the user's server-side session, never a browser token.
 *  3. Translate responses with lib/data/normalize.ts so pages stay unchanged.
 *  4. Do not put customer-specific responses in a shared cache.
 */
function unavailable(): never {
  const configured = process.env.BACKEND_API_URL ? `BACKEND_API_URL is set to ${process.env.BACKEND_API_URL}, but` : "BACKEND_API_URL is not set and";
  throw new DataSourceUnavailableError(
    `DATA_SOURCE=http is selected. ${configured} the Capital Insight backend integration is not implemented yet. ` +
      "Set DATA_SOURCE=mock (or remove it) to use demo data.",
  );
}

export const httpProvider: DataProvider = {
  kind: "http",
  getDashboard: async () => unavailable(),
  getInsights: async () => unavailable(),
  listConnections: async () => unavailable(),
  getConsentStep: async () => unavailable(),
  requestCode: async () => unavailable(),
  verifyCode: async () => unavailable(),
  disconnect: async () => unavailable(),
  resetDemo: async () => unavailable(),
  listAccounts: async () => unavailable(),
  getAccount: async () => unavailable(),
  listTransactions: async () => unavailable(),
  listLoanOffers: async () => unavailable(),
  listLoanApplications: async () => unavailable(),
  getLoanSchedule: async () => unavailable(),
  submitLoanApplication: async () => unavailable(),
  listMortgageOffers: async () => unavailable(),
  listMortgageApplications: async () => unavailable(),
  getMortgageSchedule: async () => unavailable(),
  submitMortgageApplication: async () => unavailable(),
};

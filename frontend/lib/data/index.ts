import "server-only";
import { httpProvider } from "./http-provider";
import { mockProvider } from "./mock-provider";
import type { DataProvider, DataSourceKind } from "./provider";

/**
 * Selects the data provider on the server from DATA_SOURCE:
 *   unset or "mock" -> fixtures (default, no .env.local needed)
 *   "http"          -> future main backend (currently fails loudly)
 * Any other value is a configuration error, never a silent fallback.
 */
export function dataSourceKind(): DataSourceKind {
  const value = (process.env.DATA_SOURCE ?? "mock").trim().toLowerCase();
  if (value === "" || value === "mock") return "mock";
  if (value === "http") return "http";
  throw new Error(`Unsupported DATA_SOURCE "${process.env.DATA_SOURCE}". Use "mock" or "http".`);
}

export function getDataProvider(): DataProvider {
  return dataSourceKind() === "http" ? httpProvider : mockProvider;
}

export type { DataProvider, Gated, SubmitResult } from "./provider";

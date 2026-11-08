/**
 * One hook per piece of data. Each returns SWR's { data, error, isLoading, mutate }.
 *
 * Pattern for a new screen: add a hook here (copy one below), then call it in a
 * component and render its loading, error, and data states.
 */
import useSWR from "swr";

import { api, type ApiError, type Schemas, unwrap } from "./api";

export function useProfile(customerId: string) {
  return useSWR<Schemas["FinancialProfile"], ApiError>(["profile", customerId], () =>
    unwrap(
      api.GET("/api/v1/customers/{customer_id}/profile", {
        params: { path: { customer_id: customerId } },
      }),
    ),
  );
}

export function useHealthReport(customerId: string) {
  return useSWR<Schemas["HealthReport"], ApiError>(["health-report", customerId], () =>
    unwrap(
      api.GET("/api/v1/customers/{customer_id}/health-report", {
        params: { path: { customer_id: customerId } },
      }),
    ),
  );
}

export function useCashFlow(customerId: string, months = 3) {
  return useSWR<Schemas["CashFlowSummary"], ApiError>(["cash-flow", customerId, months], () =>
    unwrap(
      api.GET("/api/v1/customers/{customer_id}/cash-flow", {
        params: { path: { customer_id: customerId }, query: { months } },
      }),
    ),
  );
}

/**
 * Search params are user-controlled text. These helpers read them defensively
 * and report problems instead of throwing, so pages can show a validation
 * message (like the services' 422) rather than crashing.
 */
export type SearchParams = Record<string, string | string[] | undefined>;

export function firstParam(params: SearchParams, key: string): string | undefined {
  const value = params[key];
  const first = Array.isArray(value) ? value[0] : value;
  return first === undefined || first.trim() === "" ? undefined : first.trim();
}

export function parsePage(params: SearchParams): number {
  const raw = firstParam(params, "page");
  const page = raw && /^\d{1,5}$/.test(raw) ? Number(raw) : 1;
  return page >= 1 ? page : 1;
}

/** Valid YYYY-MM-DD calendar date (rejects 2026-02-30). */
export function isIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

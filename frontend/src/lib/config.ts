// NEXT_PUBLIC_ values are baked into the browser bundle at build time, so they must
// never hold secrets. These are just addresses. Set them in frontend/.env.local.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Until login exists, the dashboard shows one demo customer.
export const DEMO_CUSTOMER = process.env.NEXT_PUBLIC_DEMO_CUSTOMER ?? "demo-alex";

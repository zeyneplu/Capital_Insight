/** Identical synthetic-credit-v1 policy to the independent Python mock services. */
export function syntheticCreditScore(email: string): number {
  let value = 2166136261;
  for (const byte of new TextEncoder().encode(email.trim().toLowerCase()))
    value = Math.imul(value ^ byte, 16777619) >>> 0;
  return 650 + value % 151;
}

/** Labels describe this app's demo ranges, not a bureau's scoring methodology. */
export function creditScoreLabel(score: number): string {
  if (score < 580) return "Needs attention";
  if (score < 670) return "Fair";
  if (score < 740) return "Good";
  if (score < 800) return "Very good";
  return "Excellent";
}

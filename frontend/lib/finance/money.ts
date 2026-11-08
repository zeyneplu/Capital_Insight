/**
 * Decimal-safe money and rate arithmetic.
 *
 * The services send money as decimal strings ("16487.05") and rates as decimal
 * fractions ("0.0625" = 6.25%). Binary floating point cannot represent most
 * cent values exactly (0.1 + 0.2 !== 0.3), so every calculation here works on
 * integer cents stored as `bigint`, and only converts back to a decimal string
 * at the boundary. Display formatting lives in `lib/format.ts`.
 *
 * This module has no imports so it can run in the browser, on the server, and
 * under `node --test` without a bundler.
 */

/** An exact amount of money in integer cents. */
export type Cents = bigint;

/** A decimal value represented as `units / 10^scale` (e.g. "0.0625" -> 625n, 4). */
export interface ScaledDecimal {
  units: bigint;
  scale: number;
}

const MONEY_PATTERN = /^(-)?(\d+)(?:\.(\d{1,2}))?$/;
const DECIMAL_PATTERN = /^(-)?(\d+)(?:\.(\d+))?$/;

export class MoneyFormatError extends Error {
  constructor(value: unknown) {
    super(`Not a valid decimal money string: ${JSON.stringify(value)}`);
    this.name = "MoneyFormatError";
  }
}

/** Returns true when `value` is a decimal string with at most two fraction digits. */
export function isMoneyString(value: string): boolean {
  return MONEY_PATTERN.test(value.trim());
}

/** Parses "1234.5" / "1234.50" / "-3" into integer cents. Throws on anything else. */
export function toCents(value: string): Cents {
  const match = MONEY_PATTERN.exec(value.trim());
  if (!match) throw new MoneyFormatError(value);
  const [, minus, whole, fraction = ""] = match;
  const cents = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
  return minus ? -cents : cents;
}

/** Formats integer cents as a two-decimal string, the same shape the APIs use. */
export function fromCents(cents: Cents): string {
  const negative = cents < 0n;
  const abs = negative ? -cents : cents;
  const whole = abs / 100n;
  const fraction = (abs % 100n).toString().padStart(2, "0");
  return `${negative ? "-" : ""}${whole}.${fraction}`;
}

/** Parses any decimal string ("0.0625", "12", "0.8000") without losing precision. */
export function parseDecimal(value: string): ScaledDecimal {
  const match = DECIMAL_PATTERN.exec(value.trim());
  if (!match) throw new MoneyFormatError(value);
  const [, minus, whole, fraction = ""] = match;
  const units = BigInt(whole + fraction);
  return { units: minus ? -units : units, scale: fraction.length };
}

/** Renders a ScaledDecimal back to a string with exactly `scale` fraction digits. */
export function formatScaled({ units, scale }: ScaledDecimal): string {
  const negative = units < 0n;
  const digits = (negative ? -units : units).toString().padStart(scale + 1, "0");
  const whole = scale === 0 ? digits : digits.slice(0, -scale);
  const fraction = scale === 0 ? "" : `.${digits.slice(-scale)}`;
  return `${negative ? "-" : ""}${whole}${fraction}`;
}

export function pow10(exponent: number): bigint {
  return 10n ** BigInt(exponent);
}

/**
 * Integer division rounded half away from zero, matching Python's
 * `Decimal.quantize(..., rounding=ROUND_HALF_UP)` used by the services.
 */
export function divRoundHalfUp(numerator: bigint, denominator: bigint): bigint {
  if (denominator === 0n) throw new RangeError("Division by zero");
  const negative = numerator < 0n !== denominator < 0n;
  const n = numerator < 0n ? -numerator : numerator;
  const d = denominator < 0n ? -denominator : denominator;
  // floor(n/d + 1/2) == floor((2n + d) / 2d), computed exactly on integers.
  const result = (2n * n + d) / (2n * d);
  return negative ? -result : result;
}

/**
 * Integer division rounded half to even (banker's rounding), matching Python's
 * default Decimal context used by bare `.quantize()` calls.
 */
export function divRoundHalfEven(numerator: bigint, denominator: bigint): bigint {
  if (denominator === 0n) throw new RangeError("Division by zero");
  const negative = numerator < 0n !== denominator < 0n;
  const n = numerator < 0n ? -numerator : numerator;
  const d = denominator < 0n ? -denominator : denominator;
  let quotient = n / d;
  const twiceRemainder = (n % d) * 2n;
  if (twiceRemainder > d || (twiceRemainder === d && quotient % 2n === 1n)) {
    quotient += 1n;
  }
  return negative ? -quotient : quotient;
}

/**
 * Multiplies cents by a decimal rate and optional divisor, rounding half up to
 * the cent. `applyRate(balance, "0.0625", 12)` is one month of interest at
 * 6.25% APR, exactly like `(balance * apr / 12).quantize(CENT, ROUND_HALF_UP)`.
 */
export function applyRate(cents: Cents, rate: string, divisor = 1n): Cents {
  const { units, scale } = parseDecimal(rate);
  return divRoundHalfUp(cents * units, pow10(scale) * divisor);
}

export function sumCents(values: Iterable<Cents>): Cents {
  let total = 0n;
  for (const value of values) total += value;
  return total;
}

/** Sums decimal money strings exactly and returns a decimal money string. */
export function sumMoney(values: Iterable<string>): string {
  let total = 0n;
  for (const value of values) total += toCents(value);
  return fromCents(total);
}

export function minCents(a: Cents, b: Cents): Cents {
  return a < b ? a : b;
}

export function maxCents(a: Cents, b: Cents): Cents {
  return a > b ? a : b;
}

/**
 * A ratio for display only (progress bars, percent labels). Financial
 * decisions must compare exact integers instead of these approximations.
 */
export function ratioForDisplay(part: Cents, whole: Cents): number {
  if (whole === 0n) return 0;
  // Scale to basis points first so the float conversion happens on a small integer.
  return Number((part * 10_000n) / whole) / 10_000;
}

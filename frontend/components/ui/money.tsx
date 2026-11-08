import { formatMoney } from "@/lib/format";
import { cx } from "./primitives";

/**
 * Renders a decimal money string. `tone="flow"` colors credits and debits,
 * always alongside an explicit +/- sign so color is never the only cue.
 */
export function Money({
  value,
  signed = false,
  tone,
  className,
}: {
  value: string;
  signed?: boolean;
  tone?: "flow";
  className?: string;
}) {
  const negative = value.trim().startsWith("-");
  const zero = /^-?0+(\.0+)?$/.test(value.trim());
  return (
    <span className={cx("tabular-nums", tone === "flow" && !zero && (negative ? "text-text" : "text-good"), className)}>
      {formatMoney(value, { signed })}
    </span>
  );
}

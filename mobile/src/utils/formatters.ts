/**
 * Clinical and Numerical Formatting Utilities
 * Standardizes decimal precision across the entire Nutriloop mobile application.
 * All decimal displays are strictly capped at 2 decimal places (or fewer if integer/exact).
 */

/**
 * Formats a number to at most `maxPlaces` decimal places (default: 2).
 * Trims unneeded trailing zeros (e.g. 5.8 instead of 5.80, 130 instead of 130.00).
 */
export function formatDecimal(
  val: number | string | null | undefined,
  maxPlaces: number = 2
): string {
  if (val == null) return "0";
  const num = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(num)) return "0";
  if (Number.isInteger(num)) return num.toString();
  const factor = Math.pow(10, maxPlaces);
  const rounded = Math.round((num + Number.EPSILON) * factor) / factor;
  return rounded.toString();
}

/**
 * Mathematically rounds a floating point number to at most `maxPlaces` (default: 2) as a number.
 * Eliminates IEEE 754 floating point artifacts like 5.800000000000001.
 */
export function roundToDecimal(val: number, maxPlaces: number = 2): number {
  if (val == null || isNaN(val)) return 0;
  const factor = Math.pow(10, maxPlaces);
  return Math.round((val + Number.EPSILON) * factor) / factor;
}

/**
 * Formats a percentage value capped at 2 decimal places (e.g. 68.42% or 100%).
 */
export function formatPercentage(val: number | null | undefined, maxPlaces: number = 2): string {
  if (val == null || isNaN(val)) return "0%";
  return `${formatDecimal(val, maxPlaces)}%`;
}

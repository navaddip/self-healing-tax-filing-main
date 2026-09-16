/**
 * Indian Rupee (INR) formatting and parsing utilities.
 *
 * Implements strict Indian digit grouping:
 * e.g., 10000000 -> "₹ 1,00,00,000"
 */

export function formatINR(
  val?: number | string,
  includeSymbol: boolean = true,
): string {
  if (val === undefined || val === null || val === "") {
    return includeSymbol ? "₹ 0" : "0";
  }

  const num = typeof val === "string" ? parseFloat(val.replace(/[₹,\s]/g, "")) : val;
  if (isNaN(num)) return includeSymbol ? "₹ 0" : "0";

  const isNeg = num < 0;
  const absInt = Math.round(Math.abs(num)).toString();

  let formatted = "";
  if (absInt.length <= 3) {
    formatted = absInt;
  } else {
    const last3 = absInt.slice(-3);
    const rest = absInt.slice(0, -3);
    const pairs: string[] = [];
    let cur = rest;
    while (cur.length > 2) {
      pairs.unshift(cur.slice(-2));
      cur = cur.slice(0, -2);
    }
    if (cur.length > 0) {
      pairs.unshift(cur);
    }
    formatted = `${pairs.join(",")},${last3}`;
  }

  const prefix = isNeg ? "- " : "";
  return includeSymbol ? `${prefix}₹ ${formatted}` : `${prefix}${formatted}`;
}

export function formatLakhCrore(val?: number | string): string {
  if (val === undefined || val === null || val === "") return "₹ 0";
  const num = typeof val === "string" ? parseFloat(val.replace(/[₹,\s]/g, "")) : val;
  if (isNaN(num)) return "₹ 0";

  const abs = Math.abs(num);
  const sign = num < 0 ? "-" : "";

  if (abs >= 10000000) {
    return `${sign}₹ ${(abs / 10000000).toFixed(2)} Cr`;
  }
  if (abs >= 100000) {
    return `${sign}₹ ${(abs / 100000).toFixed(2)} L`;
  }
  return formatINR(num);
}

export function parseINR(val: string): number {
  if (!val) return 0;
  const clean = val.replace(/[₹,\s]/g, "");
  const res = parseFloat(clean);
  return isNaN(res) ? 0 : res;
}

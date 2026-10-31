import type { Dictionary, Locale } from "@/lib/i18n";

export function stepLabel(dict: Dictionary, kind: string): string {
  const table = dict.steps as Record<string, string>;
  return table[kind] ?? kind;
}

export function lastSegmentKind(kinds: string[]): string | null {
  for (let index = kinds.length - 1; index >= 0; index -= 1) {
    if (kinds[index].startsWith("segment.") || kinds[index].startsWith("dl.")) return kinds[index];
  }
  return kinds[kinds.length - 1] ?? null;
}

// Fixed decimals, locale separators (0,913 in French, 0.913 in English).
export function formatDecimal(
  value: number | null | undefined,
  locale: Locale,
  digits = 3,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "·";
  return new Intl.NumberFormat(locale === "fr" ? "fr-FR" : "en-GB", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

import { en } from "./en";
import { fr, type Dictionary } from "./fr";

export type Locale = "fr" | "en";

export const LOCALE_COOKIE = "lum_locale";
export const LOCALES: Locale[] = ["fr", "en"];
export const DEFAULT_LOCALE: Locale = "fr";

const dictionaries: Record<Locale, Dictionary> = { fr, en };

export function resolveLocale(value: string | undefined | null): Locale {
  return value === "en" ? "en" : value === "fr" ? "fr" : DEFAULT_LOCALE;
}

export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale];
}

export function isLocale(value: string): value is Locale {
  return (LOCALES as string[]).includes(value);
}

export { fr, en };
export type { Dictionary };

// Fill `{name}` placeholders with values.
export function interpolate(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in vars ? String(vars[key]) : match,
  );
}

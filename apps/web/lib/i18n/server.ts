// Server-only helper: never import this module from a client component.
import { cookies } from "next/headers";
import { getDictionary, resolveLocale, LOCALE_COOKIE, type Dictionary, type Locale } from ".";

export type I18n = { locale: Locale; dict: Dictionary };

// Locale comes from the `lum_locale` cookie; French is the default.
export async function getI18n(): Promise<I18n> {
  const jar = await cookies();
  const locale = resolveLocale(jar.get(LOCALE_COOKIE)?.value);
  return { locale, dict: getDictionary(locale) };
}

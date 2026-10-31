"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { setLocaleAction } from "@/app/actions";
import { useI18n } from "@/lib/i18n/client";
import type { Locale } from "@/lib/i18n";

const options: { value: Locale; label: "shortFr" | "shortEn"; full: "fr" | "en" }[] = [
  { value: "fr", label: "shortFr", full: "fr" },
  { value: "en", label: "shortEn", full: "en" },
];

export function LocaleSwitch({ tone = "paper" }: { tone?: "paper" | "stage" }) {
  const { locale, dict } = useI18n();
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function change(value: Locale) {
    if (value === locale || pending) return;
    startTransition(async () => {
      await setLocaleAction(value);
      router.refresh();
    });
  }

  return (
    <div
      className={`flex items-center gap-1 ${tone === "stage" ? "text-stage-ink-soft" : "text-ink-soft"}`}
      role="group"
      aria-label={dict.locale.label}
    >
      {options.map((option, index) => (
        <span key={option.value} className="flex items-center">
          {index > 0 && <span aria-hidden="true" className="px-1 opacity-40">/</span>}
          <button
            type="button"
            lang={option.full}
            aria-pressed={locale === option.value}
            title={dict.locale[option.full]}
            onClick={() => change(option.value)}
            className={`num px-1 py-1 text-12 tracking-wide transition-colors duration-[120ms] hover:text-current ${
              locale === option.value ? "text-current opacity-100" : "opacity-55"
            }`}
          >
            {dict.locale[option.label]}
          </button>
        </span>
      ))}
    </div>
  );
}

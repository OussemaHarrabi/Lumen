import Link from "next/link";
import type { Dictionary } from "@/lib/i18n";
import { Glyph } from "@/components/ui/Glyph";
import { LocaleSwitch } from "./LocaleSwitch";

// Site header, shared by the landing page.
export function SiteHeader({ dict }: { dict: Dictionary }) {
  return (
    <header className="border-b border-rule">
      <a
        href="#contenu"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:bg-paper focus:px-3 focus:py-2 focus:text-13 focus:text-ink"
      >
        {dict.nav.skip}
      </a>
      <div className="shell flex h-[72px] items-center justify-between gap-6">
        <Link href="/" className="flex items-baseline gap-3">
          <span className="font-display text-26 leading-none tracking-[-0.01em]">{dict.site.name}</span>
          <span className="eyebrow hidden sm:inline">{dict.site.tagline}</span>
        </Link>

        <nav aria-label={dict.site.name} className="flex items-center gap-4 md:gap-6">
          <a href="#modules" className="hidden text-15 text-ink-soft transition-colors hover:text-ink md:inline">
            {dict.nav.modules}
          </a>
          <a href="#methode" className="hidden text-15 text-ink-soft transition-colors hover:text-ink md:inline">
            {dict.nav.method}
          </a>
          <Link
            href="/recalage"
            className="hidden text-15 text-ink-soft transition-colors hover:text-ink lg:inline"
          >
            {dict.nav.registration}
          </Link>
          <span aria-hidden="true" className="hidden h-4 w-px bg-rule md:block" />
          <LocaleSwitch />
          <Link href="/app" className="btn btn-secondary h-9 gap-1.5 px-3 text-13">
            <span className="hidden sm:inline">{dict.nav.open}</span>
            <span className="sm:hidden">{dict.nav.workspace}</span>
            <Glyph name="arrow-right" size={16} />
          </Link>
        </nav>
      </div>
    </header>
  );
}

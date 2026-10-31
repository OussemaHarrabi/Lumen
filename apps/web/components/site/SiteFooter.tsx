import Link from "next/link";
import type { Dictionary } from "@/lib/i18n";

// Footer: fine print, mono, no decoration.
export function SiteFooter({ dict }: { dict: Dictionary }) {
  return (
    <footer className="mt-24 border-t border-rule">
      <div className="shell grid-12 gap-y-10 py-12">
        <div className="col-span-12 md:col-span-4">
          <p className="font-display text-26 leading-none">{dict.site.name}</p>
          <p className="mt-3 max-w-[30ch] text-13 text-ink-soft">{dict.site.tagline}</p>
          <p className="mt-6 num text-12 text-ink-faint">{dict.site.course}</p>
        </div>

        {dict.footer.columns.map((column) => (
          <nav
            key={column.title}
            aria-label={column.title}
            className="col-span-6 md:col-span-3 md:col-start-auto"
          >
            <p className="caption-index">{column.title}</p>
            <ul className="mt-3 space-y-2">
              {column.links.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-13 text-ink-soft underline decoration-rule decoration-1 underline-offset-4 transition-colors hover:text-ink hover:decoration-ink"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>

      <div className="shell flex flex-col gap-2 border-t border-rule py-5 text-12 text-ink-faint sm:flex-row sm:items-center sm:justify-between">
        <span className="num">
          {dict.site.name} · {dict.site.course} · {dict.site.year}
        </span>
        <span className="num">
          {dict.footer.rights} · {dict.footer.built}
        </span>
      </div>
    </footer>
  );
}

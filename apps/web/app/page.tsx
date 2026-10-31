import Link from "next/link";
import { Glyph } from "@/components/ui/Glyph";
import { PlateFigure } from "@/components/site/PlateFigure";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { getI18n } from "@/lib/i18n/server";

export default async function Home() {
  const { dict } = await getI18n();
  const { hero, modules, method, cta } = dict;

  return (
    <>
      <SiteHeader dict={dict} />
      <main id="contenu">
        {/* Hero: text on five columns, plate on seven, never centred */}
        <section className="shell pt-14 md:pt-20">
          <div className="grid-12 items-start gap-y-14">
            <div className="col-span-12 lg:col-span-5">
              <p className="eyebrow">{hero.eyebrow}</p>
              <h1 className="display-xl mt-7">{hero.title}</h1>
              <p className="measure mt-7 text-16 text-ink-soft">{hero.lede}</p>

              <div className="mt-10 flex flex-wrap items-center gap-3">
                <Link href="/app" className="btn btn-primary gap-2">
                  {hero.primary}
                  <Glyph name="arrow-right" size={17} />
                </Link>
                <a href="#methode" className="btn btn-secondary">
                  {hero.secondary}
                </a>
              </div>

              <dl className="mt-14 grid grid-cols-3 gap-x-6 border-t border-rule pt-5">
                {hero.stats.map((stat) => (
                  <div key={stat.label}>
                    <dd className="num text-26 leading-none tabular-nums">{stat.value}</dd>
                    <dt className="mt-2 text-13 text-ink">{stat.label}</dt>
                    <dd className="mt-1 hidden text-12 leading-snug text-ink-faint sm:block">
                      {stat.detail}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>

            <div className="col-span-12 lg:col-span-7 lg:col-start-6">
              <PlateFigure />
            </div>
          </div>
        </section>

        {/* Modules: an index, not a grid of cards */}
        <section id="modules" className="shell pt-24 md:pt-32">
          <div className="grid-12 items-end gap-y-6">
            <div className="col-span-12 md:col-span-6">
              <p className="eyebrow">{modules.eyebrow}</p>
              <h2 className="display-l mt-4">{modules.title}</h2>
            </div>
            <p className="measure col-span-12 text-15 text-ink-soft md:col-span-5 md:col-start-8">
              {modules.lede}
            </p>
          </div>

          <div className="mt-12 border-t border-rule">
            <div className="grid-12 hidden py-2 md:grid" aria-hidden="true">
              <span className="caption-index col-span-1">{modules.columns.index}</span>
              <span className="caption-index col-span-4">{modules.columns.name}</span>
              <span className="caption-index col-span-5">{modules.columns.content}</span>
              <span className="caption-index col-span-2 text-right">{modules.columns.steps}</span>
            </div>

            <ol>
              {modules.items.map((item) => (
                <li key={item.id} className="group border-t border-rule">
                  <div className="grid-12 items-baseline gap-y-3 py-6">
                    <span className="num col-span-2 text-13 text-ink-faint md:col-span-1">
                      {item.index}
                    </span>
                    <div className="col-span-10 md:col-span-4">
                      <h3 className="display-m text-20 leading-snug underline-offset-4 group-hover:underline group-hover:decoration-rule">
                        {item.name}
                      </h3>
                      <ul className="mt-2.5 flex flex-wrap gap-1.5">
                        {item.techniques.map((technique) => (
                          <li key={technique} className="chip">
                            {technique}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <p className="col-span-12 max-w-[46ch] text-15 leading-relaxed text-ink-soft md:col-span-5">
                      {item.description}
                    </p>
                    <p className="num col-span-12 text-13 text-ink-faint md:col-span-2 md:text-right">
                      {item.steps} {modules.columns.steps.toLocaleLowerCase(dict.htmlLang)}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Method: three beats, one rule each */}
        <section id="methode" className="shell pt-24 md:pt-32">
          <div className="grid-12 items-end gap-y-6">
            <div className="col-span-12 md:col-span-6">
              <p className="eyebrow">{method.eyebrow}</p>
              <h2 className="display-l mt-4">{method.title}</h2>
            </div>
            <p className="measure col-span-12 text-15 text-ink-soft md:col-span-5 md:col-start-8">
              {method.lede}
            </p>
          </div>

          <ol className="mt-12 grid-12 gap-y-12">
            {method.steps.map((step) => (
              <li key={step.index} className="col-span-12 border-t border-rule pt-6 md:col-span-4">
                <span className="num text-13 text-ink-faint">{step.index}</span>
                <h3 className="display-m mt-7">{step.title}</h3>
                <p className="mt-3 max-w-[38ch] text-15 leading-relaxed text-ink-soft">{step.body}</p>
                <p className="num mt-7 text-12 tracking-wide text-ink-faint">{step.detail}</p>
                <p className="num mt-1 text-12 text-ink-faint opacity-70">{step.meta}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* Closing call to action */}
        <section className="shell pt-24 md:pt-32">
          <div className="grid-12 items-start gap-y-10 border-t border-rule pt-10">
            <div className="col-span-12 md:col-span-7">
              <p className="eyebrow">{cta.eyebrow}</p>
              <h2 className="display-l mt-4 max-w-[22ch]">{cta.title}</h2>
              <p className="measure mt-5 text-16 text-ink-soft">{cta.body}</p>
            </div>
            <div className="col-span-12 md:col-span-4 md:col-start-9">
              <Link href="/app" className="btn btn-primary w-full gap-2 sm:w-auto">
                {cta.action}
                <Glyph name="arrow-right" size={17} />
              </Link>
              <p className="num mt-3 text-12 text-ink-faint">{cta.note}</p>
              <ul className="mt-8 space-y-2 border-t border-rule pt-4">
                {cta.list.map((item) => (
                  <li key={item} className="flex items-center gap-2 text-13 text-ink-soft">
                    <Glyph name="check" size={15} className="text-ink-faint" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter dict={dict} />
    </>
  );
}

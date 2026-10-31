"use client";

import Image from "next/image";
import { useState } from "react";
import { useI18n } from "@/lib/i18n/client";

const IMAGE = "/demo/frame442.png";
const MASK = "/demo/frame442-mask.png";
const CONTOUR = "/demo/frame442-contour.png";

// Editorial plate: source image and segmented overlay on the dark stage.
export function PlateFigure() {
  const { dict } = useI18n();
  const { figure } = dict.hero;
  const [split, setSplit] = useState(56);

  return (
    <figure className="m-0">
      <div className="stage relative overflow-hidden">
        <div className="flex items-baseline justify-between gap-4 border-b border-stage-rule px-5 py-3 md:px-7">
          <span className="num text-12 tracking-[0.06em] text-stage-ink uppercase">
            {figure.index}
          </span>
          <span className="num text-12 text-stage-ink-soft">640 × 480 · 3 · PNG</span>
        </div>

        <div className="px-5 py-5 md:px-7 md:py-7">
          <div className="relative mx-auto aspect-[4/3] w-full max-w-[720px]">
            <Image
              src={IMAGE}
              alt={figure.title}
              fill
              priority
              sizes="(min-width: 1280px) 720px, (min-width: 1024px) 58vw, 100vw"
              className="object-contain"
            />
            <div
              className="pointer-events-none absolute inset-0"
              style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
              aria-hidden="true"
            >
              <div
                className="absolute inset-0 bg-series-1"
                style={{
                  maskImage: `url(${MASK})`,
                  maskSize: "100% 100%",
                  maskRepeat: "no-repeat",
                  WebkitMaskImage: `url(${MASK})`,
                  WebkitMaskSize: "100% 100%",
                  WebkitMaskRepeat: "no-repeat",
                  opacity: 0.4,
                }}
              />
              <div
                className="absolute inset-0 bg-series-4"
                style={{
                  maskImage: `url(${CONTOUR})`,
                  maskSize: "100% 100%",
                  maskRepeat: "no-repeat",
                  WebkitMaskImage: `url(${CONTOUR})`,
                  WebkitMaskSize: "100% 100%",
                  WebkitMaskRepeat: "no-repeat",
                  opacity: 0.92,
                }}
              />
            </div>

            <div
              className="pointer-events-none absolute inset-y-0 z-10 w-[2px] bg-paper shadow-[0_0_12px_rgb(0_0_0_/_0.45)]"
              style={{ left: `calc(${split}% - 1px)` }}
              aria-hidden="true"
            />

            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={split}
              onChange={(event) => setSplit(Number(event.target.value))}
              aria-label={figure.cursor}
              aria-valuetext={`${split} ${dict.units.percent}`}
              className="absolute inset-0 z-20 h-full w-full cursor-ew-resize appearance-none bg-transparent opacity-0"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-stage-rule px-5 py-3 md:px-7">
          <ul className="flex items-center gap-5">
            <li className="flex items-center gap-2">
              <span className="swatch bg-series-1" aria-hidden="true" />
              <span className="num text-12 text-stage-ink-soft">{figure.legendMask}</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="swatch bg-series-4" aria-hidden="true" />
              <span className="num text-12 text-stage-ink-soft">{figure.legendContour}</span>
            </li>
          </ul>
          <span className="num text-12 text-stage-ink-soft">
            {figure.fraction} · {figure.hint}
          </span>
        </div>
      </div>

      <figcaption className="mt-4 border-t border-rule pt-3">
        <span className="caption-index">{figure.index}</span>
        <span className="caption-index mx-2 opacity-50" aria-hidden="true">
          ·
        </span>
        <span className="text-13 font-medium text-ink">{figure.title}</span>
        <p className="caption measure mt-1.5">{figure.caption}</p>
      </figcaption>
    </figure>
  );
}

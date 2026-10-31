"use client";

import { Glyph } from "@/components/ui/Glyph";
import type { Dictionary, Locale } from "@/lib/i18n";

type Props = {
  dict: Dictionary;
  locale: Locale;
  scale: number;
  compare: boolean;
  layers: boolean;
  measures: boolean;
  running: boolean;
  progress: number;
  disabled: boolean;
  onFit: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onActual: () => void;
  onToggleCompare: () => void;
  onToggleLayers: () => void;
  onToggleMeasures: () => void;
  onRun: () => void;
  onOpenRail: () => void;
};

export function StageToolbar({
  dict,
  locale,
  scale,
  compare,
  layers,
  measures,
  running,
  progress,
  disabled,
  onFit,
  onZoomIn,
  onZoomOut,
  onActual,
  onToggleCompare,
  onToggleLayers,
  onToggleMeasures,
  onRun,
  onOpenRail,
}: Props) {
  const copy = dict.workspace.toolbar;
  const percent = new Intl.NumberFormat(locale === "fr" ? "fr-FR" : "en-GB", {
    maximumFractionDigits: 0,
  }).format(scale * 100);

  return (
    <div className="relative shrink-0 border-b border-stage-rule bg-stage-raised text-stage-ink">
      <div className="flex h-[48px] items-center gap-1 px-2 sm:px-3">
        <button
          type="button"
          onClick={onOpenRail}
          className="stage-tool lg:hidden"
          aria-label={dict.workspace.rail.label}
        >
          <Glyph name="image" size={16} />
        </button>

        <button type="button" onClick={onFit} className="stage-tool" aria-label={copy.fit} title={copy.fit}>
          <Glyph name="fit" size={16} />
          <span className="hidden text-13 lg:inline">{copy.fit}</span>
        </button>
        <button
          type="button"
          onClick={onZoomOut}
          className="stage-tool"
          aria-label={copy.zoomOut}
          title={copy.zoomOut}
        >
          <Glyph name="zoom-out" size={16} />
        </button>
        <span className="num min-w-[46px] px-1 text-center text-12 text-stage-ink">
          {disabled ? "·" : `${percent} ${dict.units.percent}`}
        </span>
        <button
          type="button"
          onClick={onZoomIn}
          className="stage-tool"
          aria-label={copy.zoomIn}
          title={copy.zoomIn}
        >
          <Glyph name="zoom-in" size={16} />
        </button>
        <button type="button" onClick={onActual} className="stage-tool" title={copy.actual} aria-label={copy.actual}>
          <Glyph name="actual" size={16} />
        </button>

        <span aria-hidden="true" className="mx-1 h-5 w-px bg-stage-rule" />

        <button
          type="button"
          onClick={onToggleLayers}
          aria-pressed={layers}
          className="stage-tool"
          title={copy.layers}
        >
          <Glyph name="layers" size={16} />
          <span className="hidden text-13 sm:inline">{copy.layers}</span>
        </button>
        <button
          type="button"
          onClick={onToggleCompare}
          aria-pressed={compare}
          disabled={disabled}
          className="stage-tool"
          title={copy.compare}
        >
          <Glyph name="compare" size={16} />
          <span className="hidden text-13 sm:inline">{copy.compare}</span>
        </button>
        <button
          type="button"
          onClick={onToggleMeasures}
          aria-pressed={measures}
          className="stage-tool"
          title={copy.measure}
        >
          <Glyph name="measure" size={16} />
          <span className="hidden text-13 sm:inline">{copy.measure}</span>
        </button>

        <span className="flex-1" />

        {running && (
          <span className="num mr-2 hidden items-center gap-2 text-12 text-stage-ink-soft md:flex">
            <span className="h-[6px] w-[6px] animate-pulse rounded-full bg-signal" aria-hidden="true" />
            {copy.running} {Math.round(progress * 100)} {dict.units.percent}
          </span>
        )}

        <button
          type="button"
          onClick={onRun}
          disabled={disabled || running}
          className="btn btn-signal h-8 px-3 text-13"
        >
          <Glyph name="arrow-right" size={15} />
          {running ? copy.running : copy.run}
        </button>
      </div>

      <div
        role="progressbar"
        aria-label={copy.progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={running ? Math.round(progress * 100) : 0}
        className="absolute inset-x-0 bottom-0 h-[2px] bg-transparent"
      >
        <div
          className="h-full bg-signal transition-[width] duration-[320ms] ease-out"
          style={{ width: running ? `${Math.max(2, progress * 100)}%` : "0%" }}
        />
      </div>
    </div>
  );
}

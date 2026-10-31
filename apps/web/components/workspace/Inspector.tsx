"use client";

import { useState, type ReactNode } from "react";
import { Glyph } from "@/components/ui/Glyph";
import type {
  AnalysisResult,
  Asset,
  PipelineSchema,
  Preset,
  Step,
} from "@/lib/api/types";
import { defaultParams } from "@/lib/api/pipeline";
import type { Dictionary, Locale } from "@/lib/i18n";
import { formatDecimal, stepLabel } from "@/lib/workspace/labels";
import type { LayerSettings, WorkspaceTab } from "./types";

type Props = {
  dict: Dictionary;
  locale: Locale;
  tab: WorkspaceTab;
  onTab: (tab: WorkspaceTab) => void;
  asset: Asset | null;
  maskAsset: Asset | null;
  steps: Step[];
  schema: PipelineSchema | null;
  onStepsChange: (steps: Step[]) => void;
  layers: LayerSettings;
  onLayersChange: (layers: LayerSettings) => void;
  result: AnalysisResult | null;
  presets: Preset[];
  onApplyPreset: (preset: Preset) => void;
  hintMissing: boolean;
  hintSlug: string | null;
  onLoadHint: () => void;
  running: boolean;
  progress: number;
  histogram: number[];
  onClose?: () => void;
};

export function Inspector({
  dict,
  locale,
  tab,
  onTab,
  asset,
  maskAsset,
  steps,
  schema,
  onStepsChange,
  layers,
  onLayersChange,
  result,
  presets,
  onApplyPreset,
  hintMissing,
  hintSlug,
  onLoadHint,
  running,
  progress,
  histogram,
  onClose,
}: Props) {
  const copy = dict.workspace.inspector;
  const tabs: { id: WorkspaceTab; label: string }[] = [
    { id: "method", label: copy.tabs.method },
    { id: "layers", label: copy.tabs.layers },
    { id: "measures", label: copy.tabs.measures },
  ];

  return (
    <aside
      aria-label={copy.label}
      className="flex h-full min-h-0 flex-col border-l border-rule bg-paper"
    >
      <div className="flex h-[44px] shrink-0 items-center justify-between border-b border-rule pl-4 pr-2">
        <span className="caption-index">{copy.label}</span>
        <button
          type="button"
          onClick={onClose}
          aria-label={dict.nav.shortcutsClose}
          className="btn-quiet xl:hidden"
        >
          <Glyph name="close" size={16} />
        </button>
      </div>

      <div role="tablist" aria-label={copy.label} className="flex shrink-0 items-baseline border-b border-rule px-4">
        {tabs.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            id={`tab-${entry.id}`}
            aria-selected={tab === entry.id}
            aria-controls={`panel-${entry.id}`}
            tabIndex={tab === entry.id ? 0 : -1}
            onClick={() => onTab(entry.id)}
            onKeyDown={(event) => {
              if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
              event.preventDefault();
              const index = tabs.findIndex((item) => item.id === tab);
              const next =
                event.key === "ArrowRight"
                  ? tabs[(index + 1) % tabs.length]
                  : tabs[(index - 1 + tabs.length) % tabs.length];
              onTab(next.id);
              document.getElementById(`tab-${next.id}`)?.focus();
            }}
            className="tab"
          >
            {entry.label}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id={`panel-${tab}`}
        aria-labelledby={`tab-${tab}`}
        className="min-h-0 flex-1 overflow-y-auto"
      >
        {tab === "method" && (
          <MethodPanel
            dict={dict}
            locale={locale}
            asset={asset}
            maskAsset={maskAsset}
            steps={steps}
            schema={schema}
            onStepsChange={onStepsChange}
            presets={presets}
            onApplyPreset={onApplyPreset}
            hintMissing={hintMissing}
            hintSlug={hintSlug}
            onLoadHint={onLoadHint}
            result={result}
            running={running}
            progress={progress}
          />
        )}
        {tab === "layers" && (
          <LayersPanel
            dict={dict}
            locale={locale}
            layers={layers}
            onLayersChange={onLayersChange}
            histogram={histogram}
          />
        )}
        {tab === "measures" && (
          <MeasuresPanel dict={dict} locale={locale} result={result} steps={steps} />
        )}
      </div>
    </aside>
  );
}

function MethodPanel({
  dict,
  locale,
  asset,
  maskAsset,
  steps,
  schema,
  onStepsChange,
  presets,
  onApplyPreset,
  hintMissing,
  hintSlug,
  onLoadHint,
  result: analysisResult,
  running,
  progress,
}: {
  dict: Dictionary;
  locale: Locale;
  asset: Asset | null;
  maskAsset: Asset | null;
  steps: Step[];
  schema: PipelineSchema | null;
  onStepsChange: (steps: Step[]) => void;
  presets: Preset[];
  onApplyPreset: (preset: Preset) => void;
  hintMissing: boolean;
  hintSlug: string | null;
  onLoadHint: () => void;
  result: AnalysisResult | null;
  running: boolean;
  progress: number;
}) {
  const copy = dict.workspace.inspector;
  const [addition, setAddition] = useState("");
  const catalogue = schema?.steps ?? [];
  const selectedKind = addition || catalogue[0]?.kind || "";

  function updateParam(index: number, key: string, value: unknown) {
    onStepsChange(
      steps.map((step, position) =>
        position === index ? { ...step, params: { ...step.params, [key]: value } } : step,
      ),
    );
  }

  function move(index: number, delta: number) {
    const next = [...steps];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    onStepsChange(next);
  }

  function addStep() {
    const spec = catalogue.find((entry) => entry.kind === selectedKind);
    if (!spec) return;
    onStepsChange([...steps, { kind: spec.kind, params: defaultParams(spec) }]);
  }

  return (
    <div className="px-4 pb-6">
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 border-b border-rule py-4 text-13">
        <dt className="text-ink-faint">{copy.target}</dt>
        <dd className="truncate text-right num text-12 text-ink">
          {asset ? asset.filename : copy.noTarget}
        </dd>
        <dt className="text-ink-faint">{copy.referenceMask}</dt>
        <dd className="truncate text-right num text-12 text-ink-soft">
          {maskAsset ? maskAsset.filename : copy.noReference}
        </dd>
      </dl>

      {presets.length > 0 && (
        <div className="border-b border-rule pt-4 pb-3">
          <h2 className="caption-index">{copy.presets}</h2>
          <ul className="mt-2 space-y-1">
            {presets.map((preset) => (
              <li key={preset.slug}>
                <button
                  type="button"
                  onClick={() => onApplyPreset(preset)}
                  title={locale === "fr" ? preset.description_fr : preset.description_en}
                  className="flex w-full items-baseline justify-between gap-3 border border-transparent px-1.5 py-1 text-left text-13 text-ink-soft transition-colors hover:border-rule hover:bg-paper-sunk hover:text-ink"
                >
                  <span className="min-w-0 truncate">
                    {locale === "fr" ? preset.label_fr : preset.label_en}
                  </span>
                  <span className="num shrink-0 text-11 text-ink-faint">
                    {formatDecimal(preset.expected_dice, locale)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {hintMissing && hintSlug && (
            <p className="mt-2 flex flex-wrap items-center gap-1.5 text-12 leading-snug text-ink-faint">
              {copy.presetHint.replace("{slug}", hintSlug)}
              <button
                type="button"
                onClick={onLoadHint}
                className="underline decoration-rule underline-offset-4 hover:text-ink"
              >
                {copy.loadHint}
              </button>
            </p>
          )}
        </div>
      )}

      <div className="flex items-baseline justify-between pt-4">
        <h2 className="caption-index">{copy.pipeline}</h2>
        <span className="num text-11 text-ink-faint">
          {steps.length} {copy.pipelineCount}
        </span>
      </div>

      <ol className="mt-2">
        {steps.map((step, index) => {
          const spec = catalogue.find((entry) => entry.kind === step.kind);
          return (
            <li key={`${step.kind}-${index}`} className="border-t border-rule py-3">
              <div className="flex items-center gap-2">
                <span className="num w-4 text-11 text-ink-faint">{String(index + 1).padStart(2, "0")}</span>
                <h3 className="min-w-0 flex-1 truncate text-13 font-medium text-ink">
                  {stepLabel(dict, step.kind)}
                </h3>
                {typeof analysisResult?.steps[index]?.duration_ms === "number" && (
                  <span className="num text-11 text-ink-faint">
                    {formatDecimal(analysisResult.steps[index].duration_ms, locale, 0)} {dict.units.ms}
                  </span>
                )}
                <span className="flex items-center gap-0.5">
                  <IconAction
                    label={copy.moveUp}
                    disabled={index === 0}
                    onClick={() => move(index, -1)}
                  >
                    <Glyph name="chevron-up" size={13} />
                  </IconAction>
                  <IconAction
                    label={copy.moveDown}
                    disabled={index === steps.length - 1}
                    onClick={() => move(index, 1)}
                  >
                    <Glyph name="chevron-down" size={13} />
                  </IconAction>
                  <IconAction
                    label={copy.removeStep}
                    onClick={() => onStepsChange(steps.filter((_, position) => position !== index))}
                  >
                    <Glyph name="close" size={13} />
                  </IconAction>
                </span>
              </div>

              {spec && spec.params.length > 0 && (
                <div className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-2.5 pl-6">
                  {spec.params.map((param) => {
                    const fieldId = `${index}-${param.key}`;
                    const value = step.params[param.key];
                    if (param.type === "boolean") {
                      return (
                        <label
                          key={param.key}
                          htmlFor={fieldId}
                          className="col-span-2 flex items-center justify-between gap-2 py-1"
                        >
                          <span className="text-13 text-ink-soft">
                            {dict.params[param.key as keyof Dictionary["params"]] ?? param.key}
                          </span>
                          <span className="flex items-center gap-2">
                            <span className="num text-11 text-ink-faint">
                              {value ? dict.params.yes : dict.params.no}
                            </span>
                            <input
                              id={fieldId}
                              type="checkbox"
                              checked={Boolean(value)}
                              onChange={(event) => updateParam(index, param.key, event.target.checked)}
                              className="h-3.5 w-3.5"
                              style={{ accentColor: "var(--ink)" }}
                            />
                          </span>
                        </label>
                      );
                    }
                    return (
                      <label key={param.key} htmlFor={fieldId} className="block">
                        <span className="field-label mb-1 text-12">
                          {dict.params[param.key as keyof Dictionary["params"]] ?? param.key}
                        </span>
                        <input
                          id={fieldId}
                          type="number"
                          className="field"
                          value={typeof value === "number" ? value : 0}
                          min={param.minimum}
                          max={param.maximum}
                          step={param.type === "number" ? 0.1 : 1}
                          onChange={(event) => {
                            const raw = event.target.value;
                            const parsed =
                              param.type === "number" ? Number.parseFloat(raw) : Number.parseInt(raw, 10);
                            updateParam(index, param.key, Number.isFinite(parsed) ? parsed : 0);
                          }}
                        />
                      </label>
                    );
                  })}
                </div>
              )}
              {!spec && (
                <p className="mt-2 pl-6 text-12 text-ink-faint">{copy.defaultParams}</p>
              )}
            </li>
          );
        })}
      </ol>

      <div className="mt-4 border-t border-rule pt-4">
        <label htmlFor="step-kind" className="field-label">
          {copy.addStep}
        </label>
        <div className="flex items-stretch gap-2">
          <select
            id="step-kind"
            className="field min-w-0 flex-1"
            value={selectedKind}
            onChange={(event) => setAddition(event.target.value)}
          >
            {catalogue.map((entry) => (
              <option key={entry.kind} value={entry.kind}>
                {stepLabel(dict, entry.kind)}
              </option>
            ))}
          </select>
          <button type="button" onClick={addStep} className="btn btn-secondary h-9 px-3" title={copy.addStep}>
            <Glyph name="plus" size={15} />
          </button>
        </div>
        <p className="mt-3 text-12 leading-relaxed text-ink-faint">{copy.runHint}</p>
        {running && (
          <p className="num mt-2 text-12 text-signal-ink">
            {dict.status.running} · {Math.round(progress * 100)} {dict.units.percent}
          </p>
        )}
      </div>
    </div>
  );
}

function IconAction({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="btn-quiet h-6 w-6 justify-center px-0 text-ink-soft hover:text-ink disabled:opacity-30"
    >
      {children}
    </button>
  );
}

function LayersPanel({
  dict,
  locale,
  layers,
  onLayersChange,
  histogram,
}: {
  dict: Dictionary;
  locale: Locale;
  layers: LayerSettings;
  onLayersChange: (layers: LayerSettings) => void;
  histogram: number[];
}) {
  const copy = dict.workspace.inspector;
  const percent = (value: number) =>
    `${new Intl.NumberFormat(locale === "fr" ? "fr-FR" : "en-GB", { maximumFractionDigits: 0 }).format(
      value * 100,
    )} ${dict.units.percent}`;
  const peak = histogram.length ? Math.max(...histogram) : 0;

  return (
    <div className="px-4 pb-6">
      <h2 className="caption-index pt-4">{copy.layersTitle}</h2>

      <div className="mt-3 border-t border-rule">
        <div className="flex items-center justify-between gap-3 py-3">
          <label htmlFor="mask-visible" className="flex items-center gap-2 text-13 text-ink">
            <span
              className="swatch"
              style={{ backgroundColor: `var(--series-${layers.seriesIndex + 1})` }}
              aria-hidden="true"
            />
            {copy.maskLayer}
          </label>
          <input
            id="mask-visible"
            type="checkbox"
            checked={layers.maskVisible}
            onChange={(event) => onLayersChange({ ...layers, maskVisible: event.target.checked })}
            className="h-3.5 w-3.5"
            style={{ accentColor: "var(--ink)" }}
          />
        </div>

        <div className="border-t border-rule py-3">
          <div className="flex items-baseline justify-between">
            <label htmlFor="mask-opacity" className="field-label mb-0">
              {copy.opacity}
            </label>
            <span className="num text-12 text-ink-soft">{percent(layers.opacity)}</span>
          </div>
          <input
            id="mask-opacity"
            type="range"
            min={0}
            max={100}
            value={Math.round(layers.opacity * 100)}
            onChange={(event) => onLayersChange({ ...layers, opacity: Number(event.target.value) / 100 })}
            className="range mt-2"
          />
        </div>

        <div className="border-t border-rule py-3">
          <p className="field-label mb-2">{copy.series}</p>
          <div className="grid grid-cols-3 gap-x-2 gap-y-1.5">
            {dict.workspace.inspector.seriesNames.map((name, index) => (
              <button
                key={name}
                type="button"
                aria-pressed={layers.seriesIndex === index}
                onClick={() => onLayersChange({ ...layers, seriesIndex: index })}
                className={`flex items-center gap-1.5 border px-1.5 py-1 text-11 transition-colors ${
                  layers.seriesIndex === index
                    ? "border-ink-soft bg-paper-sunk text-ink"
                    : "border-transparent text-ink-soft hover:border-rule"
                }`}
              >
                <span
                  className="swatch"
                  style={{ backgroundColor: `var(--series-${index + 1})` }}
                  aria-hidden="true"
                />
                <span className="truncate">{name}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-rule py-3">
          <label htmlFor="contour-visible" className="flex items-center gap-2 text-13 text-ink">
            <span className="swatch bg-series-4" aria-hidden="true" />
            {copy.contourLayer}
          </label>
          <input
            id="contour-visible"
            type="checkbox"
            checked={layers.contourVisible}
            onChange={(event) => onLayersChange({ ...layers, contourVisible: event.target.checked })}
            className="h-3.5 w-3.5"
            style={{ accentColor: "var(--ink)" }}
          />
        </div>

        <div className="border-t border-rule py-3">
          <div className="flex items-baseline justify-between">
            <label htmlFor="contour-weight" className="field-label mb-0">
              {copy.contourWeight}
            </label>
            <span className="num text-12 text-ink-soft">
              {layers.contourWeight} {dict.units.px}
            </span>
          </div>
          <input
            id="contour-weight"
            type="range"
            min={1}
            max={3}
            value={layers.contourWeight}
            onChange={(event) =>
              onLayersChange({ ...layers, contourWeight: Number(event.target.value) })
            }
            className="range mt-2"
          />
        </div>
      </div>

      <div className="mt-5 border-t border-rule pt-4">
        <div className="flex items-baseline justify-between">
          <h2 className="caption-index">{copy.histogram}</h2>
          <span className="num text-11 text-ink-faint">{copy.histogramHint}</span>
        </div>
        {histogram.length ? (
          <div
            role="img"
            aria-label={`${copy.histogram} · ${copy.histogramHint}`}
            className="mt-3 flex h-16 items-end gap-px border-b border-rule"
          >
            {histogram.map((count, index) => (
              <span
                key={index}
                className="flex-1 bg-ink-faint"
                style={{ height: `${peak ? Math.max(1, (count / peak) * 100) : 0}%` }}
              />
            ))}
          </div>
        ) : (
          <p className="mt-2 text-12 text-ink-faint">{copy.histogramEmpty}</p>
        )}
      </div>
    </div>
  );
}

function MeasuresPanel({
  dict,
  locale,
  result,
  steps,
}: {
  dict: Dictionary;
  locale: Locale;
  result: AnalysisResult | null;
  steps: Step[];
}) {
  const copy = dict.workspace.inspector;
  if (!result) {
    return (
      <div className="px-4 py-6">
        <h2 className="caption-index">{copy.measuresTitle}</h2>
        <p className="mt-3 max-w-[34ch] text-13 leading-relaxed text-ink-faint">
          {copy.measuresEmpty}
        </p>
      </div>
    );
  }

  const metrics = result.metrics;
  const rows: { key: keyof NonNullable<typeof metrics>; label: string }[] = [
    { key: "dice", label: copy.measures.dice },
    { key: "iou", label: copy.measures.iou },
    { key: "recall", label: copy.measures.recall },
    { key: "precision", label: copy.measures.precision },
  ];

  return (
    <div className="px-4 pb-6">
      <div className="flex items-baseline justify-between pt-4">
        <h2 className="caption-index">{copy.measuresTitle}</h2>
        <span className="num text-11 text-ink-faint">
          {formatDecimal(result.total_ms, locale, 0)} {dict.units.ms}
        </span>
      </div>

      <table className="measure-table mt-2">
        <thead>
          <tr>
            <th scope="col">{copy.table.measure}</th>
            <th scope="col" className="value">
              {copy.table.value}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const value = metrics?.[row.key] ?? null;
            const isBest = row.key === "dice" && value !== null;
            return (
              <tr key={row.key} className={isBest ? "best" : undefined}>
                <th scope="row" className="font-normal text-ink-soft">
                  {row.label}
                  {isBest && (
                    <span className="ml-2 num text-11 text-signal-ink">{copy.best}</span>
                  )}
                </th>
                <td className="value">{formatDecimal(value, locale)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="mt-6">
        <h3 className="caption-index">{copy.perStep}</h3>
        <table className="measure-table mt-2">
          <thead>
            <tr>
              <th scope="col">{copy.step}</th>
              <th scope="col" className="value">
                {copy.duration}
              </th>
            </tr>
          </thead>
          <tbody>
            {result.steps.map((step, index) => (
              <tr key={`${step.kind}-${index}`}>
                <th scope="row" className="font-normal text-ink-soft">
                  <span className="num mr-2 text-11 text-ink-faint">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {stepLabel(dict, step.kind)}
                </th>
                <td className="value">
                  {formatDecimal(step.duration_ms, locale, 0)} {dict.units.ms}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {diagnosticRows(result.diagnostics, locale).length > 0 && (
        <div className="mt-6 border-t border-rule pt-4">
          <h3 className="caption-index">{copy.diagnostics}</h3>
          <dl className="mt-2 space-y-1">
            {diagnosticRows(result.diagnostics, locale).map(([key, value]) => (
              <div key={key} className="flex items-baseline justify-between gap-3">
                <dt className="num text-12 text-ink-faint">{key}</dt>
                <dd className="num text-12 text-ink">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      <p className="num mt-6 text-11 text-ink-faint">
        {steps.length} {copy.pipelineCount}
      </p>
    </div>
  );
}

// Scalar diagnostics only: nested objects are not useful in a measurement panel.
function diagnosticRows(
  diagnostics: Record<string, unknown>,
  locale: Locale,
): [string, string][] {
  const rows: [string, string][] = [];
  for (const [key, value] of Object.entries(diagnostics)) {
    if (typeof value === "number") {
      rows.push([key, Number.isInteger(value) ? String(value) : formatDecimal(value, locale, 4)]);
    } else if (typeof value === "boolean" || typeof value === "string") {
      rows.push([key, String(value)]);
    } else if (Array.isArray(value) && value.length <= 6 && value.every((item) => typeof item === "number")) {
      rows.push([key, (value as number[]).join(" · ")]);
    }
  }
  return rows;
}

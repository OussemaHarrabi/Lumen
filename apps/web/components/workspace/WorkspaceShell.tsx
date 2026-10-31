"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Glyph } from "@/components/ui/Glyph";
import { LocaleSwitch } from "@/components/site/LocaleSwitch";
import { ImageCanvas, type CanvasHandle, type CanvasStatus } from "@/components/canvas/ImageCanvas";
import { api, isDemoMode } from "@/lib/api/client";
import {
  ApiError,
  type Analysis,
  type AnalysisResult,
  type Asset,
  type Demo,
  type PipelineSchema,
  type Preset,
  type Step,
} from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/client";
import type { Dictionary, Locale } from "@/lib/i18n";
import { EmptyState } from "./EmptyState";
import { Inspector } from "./Inspector";
import { Rail } from "./Rail";
import { StageToolbar } from "./StageToolbar";
import type { LayerSettings, WorkspaceTab } from "./types";

const DEFAULT_STEPS: Step[] = [
  { kind: "preprocess.gray", params: {} },
  { kind: "preprocess.median", params: { ksize: 5 } },
  { kind: "segment.otsu", params: { invert: false } },
  { kind: "postprocess.open", params: { ksize: 3 } },
];

const DEFAULT_LAYERS: LayerSettings = {
  maskVisible: true,
  contourVisible: true,
  seriesIndex: 0,
  opacity: 0.45,
  contourWeight: 2,
};

export function WorkspaceShell({ initialEmpty }: { initialEmpty: boolean }) {
  const { locale, dict } = useI18n();

  const [demos, setDemos] = useState<Demo[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [schema, setSchema] = useState<PipelineSchema | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [assetId, setAssetId] = useState<string | null>(null);
  const [maskId, setMaskId] = useState<string | null>(null);
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>(DEFAULT_STEPS);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [histogram, setHistogram] = useState<number[]>([]);

  const [tab, setTab] = useState<WorkspaceTab>("method");
  const [layers, setLayers] = useState<LayerSettings>(DEFAULT_LAYERS);
  const [compare, setCompare] = useState(false);
  const [status, setStatus] = useState<CanvasStatus | null>(null);

  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [railOpen, setRailOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  const canvasRef = useRef<CanvasHandle>(null);
  const unsubscribers = useRef(new Set<() => void>());

  const asset = assets.find((entry) => entry.id === assetId) ?? null;
  const maskAsset = assets.find((entry) => entry.id === maskId && entry.kind === "mask") ?? null;

  const messageFor = useCallback(
    (cause: unknown) => {
      if (cause instanceof ApiError) {
        return dict.api.errors[cause.code] ?? dict.api.errors.unknown;
      }
      return dict.api.errors.unknown;
    },
    [dict],
  );

  const track = useCallback((id: string) => {
    const stop = { off: undefined as (() => void) | undefined };
    const off = api.watchAnalysis(id, (event) => {
      setProgress(event.progress);
      setAnalyses((previous) =>
        previous.map((entry) =>
          entry.id === id ? { ...entry, status: event.status, progress: event.progress } : entry,
        ),
      );
      if (event.status === "done") {
        stop.off?.();
        setRunning(false);
        setProgress(1);
        api
          .getResult(id)
          .then((output) => {
            setResult(output);
            setAnalyses((previous) =>
              previous.map((entry) =>
                entry.id === id
                  ? {
                      ...entry,
                      summary: {
                        dice: output.metrics?.dice ?? undefined,
                        iou: output.metrics?.iou ?? undefined,
                        recall: output.metrics?.recall ?? undefined,
                        precision: output.metrics?.precision ?? undefined,
                        total_ms: output.total_ms,
                      },
                    }
                  : entry,
              ),
            );
          })
          .catch(() => setError(dict.api.errors.step_failed));
      }
      if (event.status === "error") {
        stop.off?.();
        setRunning(false);
        setError(dict.api.errors.step_failed);
      }
    });
    stop.off = off;
    unsubscribers.current.add(off);
    return off;
  }, [dict]);

  // First load: assets, analyses, catalogue and samples.
  useEffect(() => {
    let cancelled = false;
    const stops = unsubscribers.current;
    (async () => {
      try {
        const [assetList, analysisList, schemaData, demoList, presetList] = await Promise.all([
          api.listAssets(),
          api.listAnalyses(),
          api.pipelineSchema(),
          api.listDemos(),
          api.getPresets(),
        ]);
        if (cancelled) return;
        setAssets(assetList);
        setAnalyses(analysisList);
        setSchema(schemaData);
        setDemos(demoList);
        setPresets(presetList);
        const firstMask = assetList.find((entry) => entry.kind === "mask");
        if (firstMask) setMaskId(firstMask.id);

        if (!initialEmpty) {
          const firstImage = assetList.find((entry) => entry.kind === "image");
          if (firstImage) {
            setAssetId(firstImage.id);
            const latest = analysisList.find(
              (entry) => entry.status === "done" && entry.asset_id === firstImage.id,
            );
            if (latest) {
              setAnalysisId(latest.id);
              if (latest.reference_mask_id) setMaskId(latest.reference_mask_id);
              setSteps(latest.steps);
              const output = await api.getResult(latest.id).catch(() => null);
              if (!cancelled && output) setResult(output);
            }
          }
        }
      } catch (cause) {
        if (!cancelled) setError(messageFor(cause));
      }
    })();
    return () => {
      cancelled = true;
      stops.forEach((off) => off());
      stops.clear();
    };
    // Runs once: the demo dataset is the starting point.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Source and mask URLs derive from the selection; no state to keep in sync.
  const imageUrl = useMemo(() => (assetId ? api.assetFileUrl(assetId) : null), [assetId]);
  const maskUrl = useMemo(() => {
    if (result?.mask_url) return result.mask_url;
    return maskAsset ? api.assetFileUrl(maskAsset.id) : null;
  }, [result, maskAsset]);

  const runAnalysis = useCallback(async () => {
    if (!assetId || !steps.length || running) return;
    setError(null);
    setResult(null);
    setRunning(true);
    setProgress(0.02);
    try {
      const analysis = await api.createAnalysis({
        asset_id: assetId,
        reference_mask_id: maskAsset?.id ?? null,
        steps,
      });
      setAnalyses((previous) => [analysis, ...previous]);
      setAnalysisId(analysis.id);
      track(analysis.id);
    } catch (cause) {
      setRunning(false);
      setError(messageFor(cause));
    }
  }, [assetId, steps, running, maskAsset, track, messageFor]);

  const selectAsset = useCallback((id: string) => {
    setAssetId(id);
    setAnalysisId(null);
    setResult(null);
    setRailOpen(false);
  }, []);

  const selectAnalysis = useCallback(
    (id: string) => {
      const analysis = analyses.find((entry) => entry.id === id);
      if (!analysis) return;
      setAssetId(analysis.asset_id);
      setAnalysisId(analysis.id);
      if (analysis.reference_mask_id) setMaskId(analysis.reference_mask_id);
      setSteps(analysis.steps);
      setResult(null);
      setRailOpen(false);
      if (analysis.status === "done") {
        setRunning(false);
        setProgress(1);
        api
          .getResult(analysis.id)
          .then(setResult)
          .catch(() => setError(dict.api.errors.step_failed));
      } else {
        setRunning(analysis.status === "running");
        setProgress(analysis.progress);
        track(analysis.id);
      }
    },
    [analyses, track, dict],
  );

  const loadDemo = useCallback(
    async (slug: string) => {
      try {
        const demo = demos.find((entry) => entry.slug === slug);
        const imagePart =
          demo?.parts.find((part) => part.kind === "image" && part.name !== "moving") ??
          demo?.parts.find((part) => part.kind === "image");
        const maskPart = demo?.parts.find((part) => part.kind === "mask");
        const created = await api.createAssetFromDemo(slug, imagePart?.name ?? "image");
        let maskAssetCreated = null;
        if (maskPart) {
          maskAssetCreated = await api.createAssetFromDemo(slug, maskPart.name);
        }
        const list = await api.listAssets();
        setAssets(list);
        if (maskAssetCreated) setMaskId(maskAssetCreated.id);
        if (created.kind === "image") selectAsset(created.id);
        setRailOpen(false);
      } catch (cause) {
        setError(messageFor(cause));
      }
    },
    [demos, selectAsset, messageFor],
  );

  const importFile = useCallback(
    async (file: File, kind: "image" | "mask" | "auto" = "auto") => {
      setImporting(true);
      setError(null);
      const looksLikeMask = /mask|masque|_gt|verite/i.test(file.name);
      const target: "image" | "mask" =
        kind === "auto" ? (looksLikeMask ? "mask" : "image") : kind;
      try {
        const created = await api.uploadAsset(file, target);
        const list = await api.listAssets();
        setAssets(list);
        if (target === "mask") {
          setMaskId(created.id);
        } else {
          selectAsset(created.id);
        }
      } catch (cause) {
        setError(messageFor(cause));
      } finally {
        setImporting(false);
      }
    },
    [selectAsset, messageFor],
  );

  const [presetHint, setPresetHint] = useState<string | null>(null);

  const applyPreset = useCallback((preset: Preset) => {
    setSteps(preset.steps.map((step) => ({ kind: step.kind, params: { ...step.params } })));
    setPresetHint(preset.asset_hint);
    setError(null);
    setTab("method");
  }, []);

  const toggleLayers = useCallback(() => {
    setTab((current) => (current === "layers" ? "method" : "layers"));
    setInspectorOpen(true);
  }, []);

  const toggleMeasures = useCallback(() => {
    setTab((current) => (current === "measures" ? "method" : "measures"));
    setInspectorOpen(true);
  }, []);

  // Global shortcuts, ignored while a form control owns the focus.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName ?? "";
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (["INPUT", "SELECT", "TEXTAREA", "BUTTON", "A"].includes(tag)) return;
      const key = event.key.toLowerCase();
      if (key === "c") setCompare((value) => !value);
      else if (key === "l") toggleLayers();
      else if (key === "m") toggleMeasures();
      else if (key === "f") canvasRef.current?.fit();
      else if (key === "1") canvasRef.current?.actualSize();
      else if (key === "escape") {
        setShortcutsOpen(false);
        setRailOpen(false);
        setInspectorOpen(false);
      } else if (event.key === "Enter") {
        void runAnalysis();
      } else if (key === "?") {
        setShortcutsOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [runAnalysis, toggleLayers, toggleMeasures]);

  const demoModeLabel = isDemoMode ? dict.workspace.demoMode : dict.workspace.liveMode;
  const canvasLabels = {
    stage: dict.workspace.stage.label,
    loading: dict.workspace.stage.loading,
    failed: dict.workspace.stage.failed,
    hint: dict.workspace.stage.hint,
    percent: dict.units.percent,
  };

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-paper">
      <header className="flex h-[52px] shrink-0 items-center justify-between gap-3 border-b border-rule bg-paper px-3 sm:px-4">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/" className="font-display text-20 leading-none">
            {dict.site.name}
          </Link>
          <span aria-hidden="true" className="hidden h-4 w-px bg-rule sm:block" />
          <h1 className="sr-only">{dict.workspace.title}</h1>
          <span className="eyebrow hidden sm:inline">{dict.workspace.breadcrumb}</span>
          <span className="num truncate text-12 text-ink-faint">
            {asset ? asset.filename : dict.workspace.stage.empty}
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <span
            className="chip hidden border-rule text-ink-faint md:inline-flex"
            title={isDemoMode ? dict.api.demoNotice : dict.workspace.liveMode}
          >
            <span
              className={`h-[5px] w-[5px] rounded-full ${isDemoMode ? "bg-series-4" : "bg-series-3"}`}
              aria-hidden="true"
            />
            {demoModeLabel}
          </span>
          <button
            type="button"
            onClick={() => setShortcutsOpen(true)}
            className="btn btn-quiet hidden items-center gap-1.5 sm:inline-flex"
            aria-label={dict.nav.shortcuts}
            title={dict.nav.shortcuts}
          >
            <Glyph name="command" size={15} />
            <span className="num text-11">{dict.nav.shortcuts}</span>
          </button>
          <Link href="/recalage" className="btn btn-quiet hidden md:inline-flex">
            {dict.nav.registration}
          </Link>
          <LocaleSwitch />
          <button
            type="button"
            onClick={() => setInspectorOpen(true)}
            className="btn-quiet xl:hidden"
            aria-label={dict.workspace.inspector.label}
          >
            <Glyph name="measure" size={17} />
          </button>
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1">
        {(railOpen || inspectorOpen) && (
          <button
            type="button"
            aria-label={dict.nav.shortcutsClose}
            onClick={() => {
              setRailOpen(false);
              setInspectorOpen(false);
            }}
            className="fixed inset-0 z-40 bg-ink/25"
          />
        )}

        <div
          className={`z-50 bg-paper max-lg:fixed max-lg:inset-y-0 max-lg:left-0 max-lg:w-[280px] max-lg:border-r max-lg:border-rule max-lg:transition-transform max-lg:duration-[220ms] max-lg:ease-out lg:static lg:w-[280px] lg:shrink-0 lg:border-r lg:border-rule ${
            railOpen ? "max-lg:translate-x-0" : "max-lg:-translate-x-full"
          }`}
        >
          <Rail
            dict={dict}
            locale={locale}
            assets={assets}
            demos={demos}
            analyses={analyses}
            selectedAssetId={assetId}
            selectedAnalysisId={analysisId}
            importing={importing}
            error={error}
            onSelectAsset={selectAsset}
            onSelectAnalysis={selectAnalysis}
            onUseDemo={(demo) => void loadDemo(demo.slug)}
            onImport={(file, kind) => void importFile(file, kind)}
            onClose={() => setRailOpen(false)}
          />
        </div>

        <main className="flex min-w-0 flex-1 flex-col">
          <StageToolbar
            dict={dict}
            locale={locale}
            scale={status?.scale ?? 0}
            compare={compare}
            layers={tab === "layers"}
            measures={tab === "measures"}
            running={running}
            progress={progress}
            disabled={!imageUrl}
            onFit={() => canvasRef.current?.fit()}
            onZoomIn={() => canvasRef.current?.zoomBy(1.25)}
            onZoomOut={() => canvasRef.current?.zoomBy(0.8)}
            onActual={() => canvasRef.current?.actualSize()}
            onToggleCompare={() => setCompare((value) => !value)}
            onToggleLayers={toggleLayers}
            onToggleMeasures={toggleMeasures}
            onRun={() => void runAnalysis()}
            onOpenRail={() => setRailOpen(true)}
          />

          <div className="relative min-h-0 flex-1 bg-stage">
            {imageUrl && asset ? (
              <ImageCanvas
                ref={canvasRef}
                imageUrl={imageUrl}
                maskUrl={maskUrl}
                layers={layers}
                compare={compare}
                onStatus={setStatus}
                onHistogram={setHistogram}
                labels={canvasLabels}
              />
            ) : (
              <EmptyState
                dict={dict}
                hasSample={demos.some((demo) => demo.kind === "image")}
                onLoadSample={() => {
                  const demo = demos.find((entry) => entry.kind === "image");
                  if (demo) void loadDemo(demo.slug);
                }}
              />
            )}

            {error && (
              <div
                role="alert"
                className="absolute inset-x-4 bottom-4 flex items-start justify-between gap-4 border border-stage-rule bg-stage-raised px-3 py-2 text-12 text-stage-ink"
              >
                <span className="leading-relaxed">{error}</span>
                <button
                  type="button"
                  onClick={() => setError(null)}
                  className="stage-tool h-6 w-6 shrink-0 px-0"
                  aria-label={dict.nav.shortcutsClose}
                >
                  <Glyph name="close" size={13} />
                </button>
              </div>
            )}
          </div>

          <StatusStrip dict={dict} locale={locale} status={status} />
        </main>

        <div
          className={`z-50 bg-paper max-xl:fixed max-xl:inset-y-0 max-xl:right-0 max-xl:w-[360px] max-xl:border-l max-xl:border-rule max-xl:transition-transform max-xl:duration-[220ms] max-xl:ease-out xl:static xl:w-[360px] xl:shrink-0 ${
            inspectorOpen ? "max-xl:translate-x-0" : "max-xl:translate-x-full"
          }`}
        >
          <Inspector
            dict={dict}
            locale={locale}
            tab={tab}
            onTab={setTab}
            asset={asset}
            maskAsset={maskAsset}
            steps={steps}
            schema={schema}
            onStepsChange={setSteps}
            layers={layers}
            onLayersChange={setLayers}
            result={result}
            presets={presets}
            onApplyPreset={applyPreset}
            hintMissing={Boolean(
              presetHint && !assets.some((entry) => entry.filename.startsWith(presetHint)),
            )}
            hintSlug={presetHint}
            onLoadHint={() => void loadDemo(presetHint ?? "")}
            running={running}
            progress={progress}
            histogram={histogram}
            onClose={() => setInspectorOpen(false)}
          />
        </div>
      </div>

      {shortcutsOpen && (
        <ShortcutsDialog dict={dict} onClose={() => setShortcutsOpen(false)} />
      )}
    </div>
  );
}

function StatusStrip({
  dict,
  locale,
  status,
}: {
  dict: Dictionary;
  locale: Locale;
  status: CanvasStatus | null;
}) {
  const copy = dict.workspace.stage;
  const pixel = status?.pixel ?? null;
  const zoom = new Intl.NumberFormat(locale === "fr" ? "fr-FR" : "en-GB", {
    maximumFractionDigits: 0,
  }).format((status?.scale ?? 0) * 100);

  return (
    <div className="flex h-[30px] shrink-0 items-center gap-2.5 overflow-hidden border-t border-stage-rule bg-stage px-3 num text-11 text-stage-ink-soft">
      <span className="shrink-0 whitespace-nowrap text-stage-ink">{copy.position}</span>
      <span className="shrink-0 whitespace-nowrap">{pixel ? `${pixel.x} · ${pixel.y}` : "·"}</span>
      <span aria-hidden="true" className="h-3 w-px shrink-0 bg-stage-rule" />
      <span className="shrink-0 whitespace-nowrap">{copy.value}</span>
      <span className="shrink-0 whitespace-nowrap text-stage-ink">
        {pixel ? `${pixel.r} ${pixel.g} ${pixel.b} · ${pixel.gray}` : "·"}
      </span>
      <span aria-hidden="true" className="h-3 w-px shrink-0 bg-stage-rule" />
      <span className="hidden shrink-0 whitespace-nowrap sm:inline">{copy.size}</span>
      <span className="hidden shrink-0 whitespace-nowrap text-stage-ink sm:inline">
        {status?.width ? `${status.width}×${status.height}` : "·"}
      </span>
      <span aria-hidden="true" className="hidden h-3 w-px shrink-0 bg-stage-rule sm:block" />
      <span className="shrink-0 whitespace-nowrap">{copy.zoom}</span>
      <span className="shrink-0 whitespace-nowrap text-stage-ink">
        {status?.loaded ? `${zoom} ${dict.units.percent}` : "·"}
      </span>
      <span className="ml-auto hidden truncate pl-4 2xl:inline">{copy.hint}</span>
    </div>
  );
}

function ShortcutsDialog({ dict, onClose }: { dict: Dictionary; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-ink/30 p-6"
      role="presentation"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        className="w-full max-w-[420px] border border-rule bg-paper-raised p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 id="shortcuts-title" className="display-m text-20">
            {dict.nav.shortcutsTitle}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="btn-quiet h-7 w-7 justify-center px-0"
            aria-label={dict.nav.shortcutsClose}
          >
            <Glyph name="close" size={15} />
          </button>
        </div>
        <dl className="mt-4 divide-y divide-rule border-t border-rule">
          {dict.workspace.shortcuts.map((entry) => (
            <div key={entry.keys} className="flex items-baseline justify-between gap-6 py-2">
              <dt className="num text-12 text-ink">{entry.keys}</dt>
              <dd className="text-right text-13 text-ink-soft">{entry.label}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}

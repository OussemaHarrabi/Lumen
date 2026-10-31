"use client";

import Link from "next/link";
import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Glyph } from "@/components/ui/Glyph";
import { LocaleSwitch } from "@/components/site/LocaleSwitch";
import { api, isDemoMode } from "@/lib/api/client";
import { ApiError, type Asset, type Demo, type Registration, type RegistrationMethod } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/client";
import { formatDecimal } from "@/lib/workspace/labels";

type View = "overlay" | "checkerboard" | "flicker";

const METHODS: RegistrationMethod[] = ["translation", "affine", "homography", "optical_flow"];

export function RegistrationShell() {
  const { locale, dict } = useI18n();
  const copy = dict.registration;

  const [assets, setAssets] = useState<Asset[]>([]);
  const [demos, setDemos] = useState<Demo[]>([]);
  const [fixedId, setFixedId] = useState<string | null>(null);
  const [movingId, setMovingId] = useState<string | null>(null);
  const [landmarks, setLandmarks] = useState<number[][]>([]);
  const [method, setMethod] = useState<RegistrationMethod>("homography");
  const [registration, setRegistration] = useState<Registration | null>(null);
  const [running, setRunning] = useState(false);
  const [loadingPair, setLoadingPair] = useState(false);
  const [view, setView] = useState<View>("overlay");
  const [landmarksSent, setLandmarksSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flickerOn, setFlickerOn] = useState(true);

  const pollTimer = useRef(0);

  const messageFor = useCallback(
    (cause: unknown) =>
      cause instanceof ApiError
        ? (dict.api.errors[cause.code] ?? dict.api.errors.unknown)
        : dict.api.errors.unknown,
    [dict],
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listAssets(), api.listDemos()])
      .then(([assetList, demoList]) => {
        if (cancelled) return;
        setAssets(assetList);
        setDemos(demoList);
        const images = assetList.filter((asset) => asset.kind === "image");
        if (images[0]) setFixedId(images[0].id);
        if (images[1]) setMovingId(images[1].id);
      })
      .catch((cause) => {
        if (!cancelled) setError(messageFor(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [messageFor]);

  // Flicker: hard alternation every 600 ms, off with reduced motion.
  useEffect(() => {
    if (view !== "flicker") return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;
    const timer = window.setInterval(() => setFlickerOn((value) => !value), 600);
    return () => window.clearInterval(timer);
  }, [view]);

  const images = assets.filter((asset) => asset.kind === "image");
  const fixed = images.find((asset) => asset.id === fixedId) ?? null;
  const moving = images.find((asset) => asset.id === movingId) ?? null;
  const fireDemo = demos.find((demo) => demo.slug === "retines-fire") ?? null;
  const metrics = registration?.metrics ?? null;
  const transform = registration?.transform ?? null;

  const register = useCallback(async () => {
    if (!fixedId || !movingId || running) return;
    setError(null);
    setRunning(true);
    setRegistration(null);
    setLandmarksSent(false);
    try {
      const created = await api.createRegistration({
        fixed_asset_id: fixedId,
        moving_asset_id: movingId,
        method,
        params: {},
      });
      setRegistration(created);
      const poll = async () => {
        try {
          const current = await api.getRegistration(created.id);
          setRegistration(current);
          if (current.status === "done") {
            setRunning(false);
            if (landmarks.length) {
              const withPoints = await api.submitLandmarks(created.id, landmarks);
              setRegistration(withPoints);
              setLandmarksSent(true);
            }
            return;
          }
          if (current.status === "error") {
            setRunning(false);
            setError(dict.registration.failure);
            return;
          }
        } catch {
          // Transient error: keep polling.
        }
        pollTimer.current = window.setTimeout(poll, 800);
      };
      pollTimer.current = window.setTimeout(poll, 600);
    } catch (cause) {
      setRunning(false);
      setError(messageFor(cause));
    }
  }, [fixedId, movingId, running, method, landmarks, messageFor, dict]);

  useEffect(
    () => () => {
      window.clearTimeout(pollTimer.current);
    },
    [],
  );

  const loadFirePair = useCallback(async () => {
    if (!fireDemo) return;
    setLoadingPair(true);
    setError(null);
    try {
      const fixedPart = fireDemo.parts.find((part) => part.name === "fixed") ?? fireDemo.parts[0];
      const movingPart = fireDemo.parts.find((part) => part.name === "moving") ?? fireDemo.parts[1];
      const nextFixed = await api.createAssetFromDemo(fireDemo.slug, fixedPart.name);
      const nextMoving = await api.createAssetFromDemo(fireDemo.slug, movingPart.name);
      const list = await api.listAssets();
      setAssets(list);
      setFixedId(nextFixed.id);
      setMovingId(nextMoving.id);
      setLandmarks(fireDemo.landmarks ?? []);
      setRegistration(null);
      setView("overlay");
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setLoadingPair(false);
    }
  }, [fireDemo, messageFor]);

  const fixedUrl = useMemo(() => (fixedId ? api.assetFileUrl(fixedId) : null), [fixedId]);
  const movingUrl = useMemo(() => (movingId ? api.assetFileUrl(movingId) : null), [movingId]);
  const percent = new Intl.NumberFormat(locale === "fr" ? "fr-FR" : "en-GB", {
    maximumFractionDigits: 0,
  });

  const viewImage =
    view === "checkerboard"
      ? registration?.checkerboard_url
      : registration?.overlay_url;
  const hasResult = Boolean(registration && registration.status === "done" && viewImage);

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-paper">
      <header className="flex h-[52px] shrink-0 items-center justify-between gap-3 border-b border-rule bg-paper px-3 sm:px-4">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/" className="font-display text-20 leading-none">
            {dict.site.name}
          </Link>
          <span aria-hidden="true" className="hidden h-4 w-px bg-rule sm:block" />
          <h1 className="text-15 font-medium">{copy.title}</h1>
          <span className="num truncate text-12 text-ink-faint">
            {fixed && moving ? `${fixed.filename} · ${moving.filename}` : copy.noPair}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <span className="chip hidden border-rule text-ink-faint md:inline-flex">
            <span
              className={`h-[5px] w-[5px] rounded-full ${isDemoMode ? "bg-series-4" : "bg-series-3"}`}
              aria-hidden="true"
            />
            {isDemoMode ? dict.workspace.demoMode : dict.workspace.liveMode}
          </span>
          <Link href="/app" className="btn btn-quiet hidden sm:inline-flex">
            {copy.backToWorkspace}
          </Link>
          <LocaleSwitch />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside
          aria-label={copy.pair}
          className="hidden w-[280px] shrink-0 flex-col overflow-y-auto border-r border-rule bg-paper md:flex"
        >
          <div className="border-b border-rule px-4 py-3">
            <p className="caption-index">{copy.pair}</p>
            <p className="mt-1.5 text-12 leading-relaxed text-ink-soft">
              {landmarks.length ? copy.landmarksCount.replace("{n}", String(landmarks.length)) : copy.hint}
            </p>
          </div>

          <div className="space-y-3 px-4 py-4">
            <button
              type="button"
              onClick={() => void loadFirePair()}
              disabled={loadingPair || !fireDemo}
              className="btn btn-secondary w-full justify-start gap-2"
            >
              <Glyph name="import" size={16} />
              {loadingPair ? copy.loadingPair : copy.loadPair}
            </button>

            <label className="block">
              <span className="field-label">{copy.selectFixed}</span>
              <select
                className="field"
                value={fixedId ?? ""}
                onChange={(event) => {
                  setFixedId(event.target.value || null);
                  setRegistration(null);
                }}
              >
                <option value="">·</option>
                {images.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.filename}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="field-label">{copy.selectMoving}</span>
              <select
                className="field"
                value={movingId ?? ""}
                onChange={(event) => {
                  setMovingId(event.target.value || null);
                  setRegistration(null);
                }}
              >
                <option value="">·</option>
                {images.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.filename}
                  </option>
                ))}
              </select>
            </label>

            <div className="border-t border-rule pt-3">
              <p className="caption-index">{copy.method}</p>
              <div role="radiogroup" aria-label={copy.method} className="mt-2 space-y-1">
                {METHODS.map((entry) => (
                  <button
                    key={entry}
                    type="button"
                    role="radio"
                    aria-checked={method === entry}
                    onClick={() => setMethod(entry)}
                    className={`flex w-full items-center justify-between border px-2 py-1.5 text-13 transition-colors ${
                      method === entry
                        ? "border-ink-soft bg-paper-sunk text-ink"
                        : "border-transparent text-ink-soft hover:border-rule"
                    }`}
                  >
                    {copy.methods[entry]}
                    {method === entry && <Glyph name="check" size={14} />}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="button"
              onClick={() => void register()}
              disabled={!fixedId || !movingId || running}
              className="btn btn-signal w-full gap-2"
            >
              <Glyph name="arrow-right" size={16} />
              {running ? copy.running : copy.run}
            </button>
            {error && (
              <p role="alert" className="text-12 leading-snug text-signal-ink">
                {error}
              </p>
            )}
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex h-[48px] shrink-0 items-center justify-between border-b border-stage-rule bg-stage-raised px-3">
            <span className="num text-12 tracking-wide text-stage-ink-soft uppercase">{copy.stage}</span>
            <div className="flex items-center gap-1" role="tablist" aria-label={copy.views.overlay}>
              {(["overlay", "checkerboard", "flicker"] as View[]).map((entry) => (
                <button
                  key={entry}
                  type="button"
                  role="tab"
                  aria-selected={view === entry}
                  disabled={!hasResult && entry !== "overlay"}
                  onClick={() => setView(entry)}
                  className="stage-tool text-12"
                  data-active={view === entry}
                >
                  {copy.views[entry]}
                </button>
              ))}
            </div>
          </div>

          <div className="relative min-h-0 flex-1 overflow-auto bg-stage">
            {!hasResult && (
              <div className="grid h-full grid-cols-1 gap-px bg-stage-rule md:grid-cols-2">
                {[
                  { id: "fixed", label: copy.fixed, asset: fixed, url: fixedUrl },
                  { id: "moving", label: copy.moving, asset: moving, url: movingUrl },
                ].map((panel) => (
                  <figure key={panel.id} className="flex min-h-0 flex-col bg-stage p-4">
                    <div className="relative min-h-0 flex-1">
                      {panel.url ? (
                        <Image
                          src={panel.url}
                          alt={panel.label}
                          fill
                          unoptimized
                          sizes="(min-width: 1280px) 40vw, 50vw"
                          className="object-contain"
                        />
                      ) : (
                        <div className="flex h-full items-center justify-center">
                          <span className="num text-12 text-stage-ink-soft">{copy.noPair}</span>
                        </div>
                      )}
                    </div>
                    <figcaption className="mt-3 border-t border-stage-rule pt-2">
                      <span className="num text-11 tracking-wide text-stage-ink-soft uppercase">
                        {panel.label}
                      </span>
                      <span className="num ml-2 text-11 text-stage-ink-soft">
                        {panel.asset ? `${panel.asset.width}×${panel.asset.height}` : "·"}
                      </span>
                    </figcaption>
                  </figure>
                ))}
              </div>
            )}

            {hasResult && (
              <div className="relative h-full p-4">
                <div className="relative h-full w-full">
                  <Image
                    src={
                      view === "flicker" && flickerOn && fixedUrl
                        ? fixedUrl
                        : (viewImage as string)
                    }
                    alt={copy.views[view]}
                    fill
                    unoptimized
                    sizes="70vw"
                    className="object-contain"
                  />
                </div>
                <span className="absolute bottom-6 left-6 num text-11 text-stage-ink-soft">
                  {copy.views[view]} · {registration?.method ? copy.methods[registration.method] : ""}
                </span>
              </div>
            )}

            {running && (
              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[2px] bg-transparent">
                <div className="h-full w-1/3 animate-pulse bg-signal" />
              </div>
            )}
          </div>
        </main>

        <aside
          aria-label={copy.result}
          className="hidden w-[360px] shrink-0 overflow-y-auto border-l border-rule bg-paper xl:block"
        >
          <div className="border-b border-rule px-4 py-3">
            <p className="caption-index">{copy.result}</p>
          </div>

          {!registration && (
            <p className="px-4 py-4 text-13 leading-relaxed text-ink-faint">{copy.noResult}</p>
          )}

          {registration && (
            <div className="px-4 pb-6">
              <table className="measure-table mt-3">
                <thead>
                  <tr>
                    <th scope="col">{copy.result}</th>
                    <th scope="col" className="value">
                      {dict.workspace.inspector.table.value}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(
                    [
                      ["mean_landmark_error", metrics?.mean_landmark_error, dict.units.px],
                      ["success_rate", metrics?.success_rate, dict.units.percent],
                      ["ncc", metrics?.ncc, ""],
                      ["mse", metrics?.mse, ""],
                      ["nmi", metrics?.nmi, ""],
                    ] as [keyof typeof copy.metrics, number | null | undefined, string][]
                  ).map(([key, value, unit]) => (
                    <tr key={key} className={key === "mean_landmark_error" ? "best" : undefined}>
                      <th scope="row" className="font-normal text-ink-soft">
                        {copy.metrics[key]}
                      </th>
                      <td className="value">
                        {formatDecimal(value ?? null, locale, key === "mse" ? 1 : 2)}
                        {unit ? ` ${unit}` : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <p className="mt-3 num text-11 text-ink-faint">
                {landmarksSent
                  ? copy.landmarksApplied
                  : landmarks.length
                    ? copy.landmarksCount.replace("{n}", String(landmarks.length))
                    : copy.landmarksMissing}
              </p>

              <div className="mt-6 border-t border-rule pt-4">
                <h2 className="caption-index">{copy.transform}</h2>
                <div className="mt-2 overflow-x-auto">
                  {transform ? (
                    <table className="num text-12 text-ink">
                      <tbody>
                        {transform.map((row, rowIndex) => (
                          <tr key={rowIndex}>
                            {row.map((value, columnIndex) => (
                              <td key={columnIndex} className="py-0.5 pr-4 text-right">
                                {value.toFixed(4)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className="text-12 text-ink-faint">{copy.empty}</p>
                  )}
                </div>
              </div>

              <dl className="mt-6 space-y-1 border-t border-rule pt-4">
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-12 text-ink-faint">{copy.fixed}</dt>
                  <dd className="num text-12 text-ink">{fixed?.filename ?? "·"}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-12 text-ink-faint">{copy.moving}</dt>
                  <dd className="num text-12 text-ink">{moving?.filename ?? "·"}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-12 text-ink-faint">{dict.status[registration.status]}</dt>
                  <dd className="num text-12 text-ink">
                    {percent.format((registration.progress ?? 0) * 100)} {dict.units.percent}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

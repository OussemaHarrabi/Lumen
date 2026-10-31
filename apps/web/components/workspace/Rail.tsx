"use client";

import Link from "next/link";
import { useRef } from "react";
import { Glyph } from "@/components/ui/Glyph";
import type { Analysis, Asset, Demo } from "@/lib/api/types";
import type { Dictionary, Locale } from "@/lib/i18n";
import { formatDecimal, lastSegmentKind, stepLabel } from "@/lib/workspace/labels";

type Props = {
  dict: Dictionary;
  locale: Locale;
  assets: Asset[];
  demos: Demo[];
  analyses: Analysis[];
  selectedAssetId: string | null;
  selectedAnalysisId: string | null;
  importing: boolean;
  error: string | null;
  onSelectAsset: (id: string) => void;
  onSelectAnalysis: (id: string) => void;
  onUseDemo: (demo: Demo) => void;
  onImport: (file: File, kind: "image" | "mask" | "auto") => void;
  onClose?: () => void;
};

const statusTone: Record<Analysis["status"], string> = {
  queued: "bg-rule-strong",
  running: "bg-signal",
  done: "bg-ink-faint",
  error: "bg-signal-ink",
};

function arrowKeys(event: React.KeyboardEvent<HTMLUListElement>) {
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  const buttons = Array.from(
    event.currentTarget.querySelectorAll<HTMLButtonElement>("button[data-rail-item]"),
  );
  const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
  if (index === -1) return;
  event.preventDefault();
  const next = event.key === "ArrowDown" ? index + 1 : index - 1;
  buttons[(next + buttons.length) % buttons.length]?.focus();
}

export function Rail({
  dict,
  locale,
  assets,
  demos,
  analyses,
  selectedAssetId,
  selectedAnalysisId,
  importing,
  error,
  onSelectAsset,
  onSelectAnalysis,
  onUseDemo,
  onImport,
  onClose,
}: Props) {
  const copy = dict.workspace.rail;
  const inputRef = useRef<HTMLInputElement>(null);
  const importKind = useRef<"image" | "mask" | "auto">("auto");
  const images = assets.filter((asset) => asset.kind === "image");
  const imageDemos = demos.filter(
    (demo) => demo.kind === "image" && !images.some((asset) => asset.filename.startsWith(demo.slug)),
  );
  const totalBytes = assets.reduce((sum, asset) => sum + asset.bytes, 0);

  return (
    <aside aria-label={copy.label} className="flex h-full min-h-0 flex-col bg-paper">
      <div className="flex h-[44px] shrink-0 items-center justify-between border-b border-rule pl-4 pr-2">
        <span className="caption-index">{copy.label}</span>
        <button
          type="button"
          onClick={onClose}
          aria-label={dict.nav.shortcutsClose}
          className="btn-quiet lg:hidden"
        >
          <Glyph name="close" size={16} />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <section aria-labelledby="rail-images" className="pb-3">
          <div className="flex items-baseline justify-between px-4 pb-1.5 pt-4">
            <h2 id="rail-images" className="caption-index">
              {copy.images}
            </h2>
            <span className="num text-11 text-ink-faint">{images.length}</span>
          </div>

          <ul onKeyDown={arrowKeys} aria-describedby="rail-hint">
            {images.map((asset) => {
              const current = asset.id === selectedAssetId;
              return (
                <li key={asset.id}>
                  <button
                    type="button"
                    data-rail-item
                    aria-current={current ? "true" : undefined}
                    aria-label={`${copy.open} ${asset.filename}`}
                    onClick={() => onSelectAsset(asset.id)}
                    className="rail-item"
                  >
                    <Glyph name="image" size={15} className="text-ink-faint" />
                    <span className="truncate text-13">{asset.filename}</span>
                    <span className="num text-11 text-ink-faint">
                      {asset.width}×{asset.height}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          {images.length === 0 && (
            <p className="px-4 py-2 text-12 leading-snug text-ink-faint">{copy.emptyImages}</p>
          )}

          {imageDemos.length > 0 && (
            <div className="mt-2 border-t border-rule pt-3">
              <p className="caption-index px-4 pb-1.5">{copy.demos}</p>
              <ul onKeyDown={arrowKeys}>
                {imageDemos.map((demo) => (
                  <li key={demo.slug}>
                    <button
                      type="button"
                      data-rail-item
                      aria-label={`${copy.useDemo} ${demo.label[locale]}`}
                      title={demo.description[locale]}
                      onClick={() => onUseDemo(demo)}
                      className="rail-item items-start"
                    >
                      <span
                        className="mt-1.5 h-[6px] w-[6px] rounded-full border border-ink-faint"
                        aria-hidden="true"
                      />
                      <span className="min-w-0 text-13 leading-snug">
                        {demo.label[locale]}
                        <span className="mt-0.5 line-clamp-2 text-11 leading-snug text-ink-faint">
                          {demo.description[locale]}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <span id="rail-hint" className="sr-only">
            {copy.navigateHint}
          </span>
        </section>

        <section aria-labelledby="rail-analyses" className="border-t border-rule pb-3 pt-1">
          <div className="flex items-baseline justify-between px-4 pb-1.5 pt-3">
            <h2 id="rail-analyses" className="caption-index">
              {copy.analyses}
            </h2>
            <span className="num text-11 text-ink-faint">{analyses.length}</span>
          </div>

          <ul onKeyDown={arrowKeys}>
            {analyses.map((analysis) => {
              const current = analysis.id === selectedAnalysisId;
              const kind = lastSegmentKind(analysis.steps.map((step) => step.kind));
              return (
                <li key={analysis.id}>
                  <button
                    type="button"
                    data-rail-item
                    aria-current={current ? "true" : undefined}
                    onClick={() => onSelectAnalysis(analysis.id)}
                    className="rail-item"
                  >
                    <span
                      className={`h-[6px] w-[6px] rounded-full ${statusTone[analysis.status]}`}
                      aria-hidden="true"
                    />
                    <span className="truncate text-13">
                      {kind ? stepLabel(dict, kind) : analysis.id}
                    </span>
                    <span className="num text-11 text-ink-faint">
                      {formatDecimal(analysis.summary?.dice, locale)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          {analyses.length === 0 && (
            <p className="px-4 py-2 text-12 text-ink-faint">{copy.noAnalyses}</p>
          )}
        </section>
      </div>

      <div className="shrink-0 space-y-2 border-t border-rule p-3">
        {images.length >= 2 && (
          <Link href="/recalage" className="btn btn-quiet w-full justify-start gap-2">
            <Glyph name="compare" size={15} />
            {dict.nav.registration}
          </Link>
        )}
        <button
          type="button"
          onClick={() => {
            importKind.current = "auto";
            inputRef.current?.click();
          }}
          disabled={importing}
          className="btn btn-secondary w-full justify-start gap-2"
        >
          <Glyph name="import" size={16} />
          {importing ? dict.workspace.import.uploading : copy.import}
        </button>
        <button
          type="button"
          onClick={() => {
            importKind.current = "mask";
            inputRef.current?.click();
          }}
          disabled={importing}
          className="btn btn-quiet w-full justify-start gap-2"
        >
          <Glyph name="layers" size={15} />
          {copy.importMask}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/tiff,image/bmp"
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onImport(file, importKind.current);
            event.target.value = "";
          }}
        />
        {error && (
          <p role="alert" className="text-12 leading-snug text-signal-ink">
            {error}
          </p>
        )}
        <p className="num text-11 text-ink-faint">
          {copy.assetsHint} · {assets.length} · {Math.round(totalBytes / 1024)}{" "}
          {dict.units.kilobyte}
        </p>
      </div>
    </aside>
  );
}

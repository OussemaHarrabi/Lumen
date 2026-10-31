"use client";

import { Glyph } from "@/components/ui/Glyph";
import type { Dictionary } from "@/lib/i18n";

// Empty state: one Fraunces title, one sentence, one action. No illustration.
export function EmptyState({
  dict,
  onLoadSample,
  hasSample,
}: {
  dict: Dictionary;
  onLoadSample: () => void;
  hasSample: boolean;
}) {
  const copy = dict.workspace.empty;
  return (
    <div className="flex h-full items-center bg-stage px-6 py-10 sm:px-10">
      <div className="max-w-[38ch]">
        <h2 className="text-26 leading-tight text-stage-ink">{copy.title}</h2>
        <p className="mt-3 text-15 leading-relaxed text-stage-ink-soft">{copy.body}</p>
        {hasSample && (
          <button
            type="button"
            onClick={onLoadSample}
            className="btn btn-secondary mt-7 border-stage-rule text-stage-ink hover:bg-stage-raised hover:text-stage-ink"
          >
            {copy.action}
            <Glyph name="arrow-right" size={16} />
          </button>
        )}
        <p className="num mt-8 text-11 text-stage-ink-soft opacity-70">{dict.workspace.stage.hint}</p>
      </div>
    </div>
  );
}

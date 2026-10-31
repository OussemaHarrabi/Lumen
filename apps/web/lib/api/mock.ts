// Demonstration backend: same shapes as the REST API, no server required.
import type {
  Analysis,
  AnalysisResult,
  AnalysisStatus,
  Asset,
  Demo,
  DemoPart,
  Health,
  PipelineSchema,
  Preset,
  Registration,
  Step,
  StepProgressEvent,
  StepResult,
} from "./types";
import { ApiError } from "./types";

const DEMO_IMAGE = "/demo/frame442.png";
const DEMO_MASK = "/demo/frame442-mask.png";

export const PIPELINE_SCHEMA: PipelineSchema = {
  steps: [
    {
      kind: "preprocess.gray",
      group: "preprocess",
      params: [],
    },
    {
      kind: "preprocess.median",
      group: "preprocess",
      params: [{ key: "ksize", type: "integer", minimum: 3, maximum: 31, default: 5 }],
    },
    {
      kind: "preprocess.gaussian",
      group: "preprocess",
      params: [
        { key: "ksize", type: "integer", minimum: 3, maximum: 31, default: 5 },
        { key: "sigma", type: "number", minimum: 0, maximum: 8, default: 0 },
      ],
    },
    {
      kind: "preprocess.mean",
      group: "preprocess",
      params: [{ key: "ksize", type: "integer", minimum: 3, maximum: 31, default: 5 }],
    },
    {
      kind: "preprocess.clahe",
      group: "preprocess",
      params: [
        { key: "clip", type: "number", minimum: 1, maximum: 8, default: 2 },
        { key: "grid", type: "integer", minimum: 2, maximum: 16, default: 8 },
      ],
    },
    {
      kind: "segment.threshold",
      group: "segment",
      params: [
        { key: "threshold", type: "integer", minimum: 0, maximum: 255, default: 110 },
        { key: "invert", type: "boolean", default: false },
      ],
    },
    {
      kind: "segment.otsu",
      group: "segment",
      params: [{ key: "invert", type: "boolean", default: false }],
    },
    {
      kind: "segment.kmeans",
      group: "segment",
      params: [
        { key: "k", type: "integer", minimum: 2, maximum: 8, default: 3 },
        { key: "seed", type: "integer", minimum: 0, maximum: 9999, default: 42 },
      ],
    },
    {
      kind: "segment.meanshift",
      group: "segment",
      params: [
        { key: "subsample", type: "integer", minimum: 1, maximum: 9, default: 3 },
        { key: "fov_restrict", type: "boolean", default: true },
      ],
    },
    {
      kind: "segment.chan_vese",
      group: "segment",
      params: [
        { key: "iterations", type: "integer", minimum: 10, maximum: 200, default: 50 },
        { key: "smoothing", type: "number", minimum: 0, maximum: 5, default: 1 },
        { key: "crop", type: "boolean", default: true },
      ],
    },
    {
      kind: "segment.watershed",
      group: "segment",
      params: [{ key: "threshold_ratio", type: "number", minimum: 0.1, maximum: 0.9, default: 0.5 }],
    },
    {
      kind: "contours.sobel",
      group: "contours",
      params: [],
    },
    {
      kind: "contours.laplace",
      group: "contours",
      params: [],
    },
    {
      kind: "contours.morph_gradient",
      group: "contours",
      params: [{ key: "ksize", type: "integer", minimum: 3, maximum: 15, default: 3 }],
    },
    {
      kind: "postprocess.open",
      group: "postprocess",
      params: [{ key: "ksize", type: "integer", minimum: 3, maximum: 15, default: 3 }],
    },
    {
      kind: "postprocess.close",
      group: "postprocess",
      params: [{ key: "ksize", type: "integer", minimum: 3, maximum: 15, default: 3 }],
    },
    {
      kind: "postprocess.largest_component",
      group: "postprocess",
      params: [],
    },
    {
      kind: "postprocess.fill_holes",
      group: "postprocess",
      params: [],
    },
    {
      kind: "dl.unet_endoscopie",
      group: "dl",
      params: [{ key: "threshold", type: "number", minimum: 0.3, maximum: 0.7, default: 0.5 }],
    },
    {
      kind: "dl.unet_busi",
      group: "dl",
      params: [{ key: "threshold", type: "number", minimum: 0.3, maximum: 0.7, default: 0.5 }],
    },
  ],
};

// Deterministic durations, in milliseconds, per step kind.
const BASE_MS: Record<string, number> = {
  "preprocess.gray": 4,
  "preprocess.median": 12,
  "preprocess.gaussian": 9,
  "preprocess.mean": 7,
  "preprocess.clahe": 21,
  "segment.threshold": 2,
  "segment.otsu": 6,
  "segment.kmeans": 118,
  "segment.meanshift": 2140,
  "segment.chan_vese": 1640,
  "segment.watershed": 240,
  "contours.sobel": 8,
  "contours.laplace": 9,
  "contours.morph_gradient": 7,
  "postprocess.open": 5,
  "postprocess.close": 6,
  "postprocess.largest_component": 11,
  "postprocess.fill_holes": 6,
  "dl.unet_endoscopie": 1120,
  "dl.unet_busi": 980,
};

const SEGMENT_SCORES: Record<string, { dice: number; iou: number; recall: number; precision: number }> = {
  "segment.otsu": { dice: 0.9125, iou: 0.8393, recall: 0.9402, precision: 0.8865 },
  "segment.kmeans": { dice: 0.8812, iou: 0.7876, recall: 0.9084, precision: 0.8557 },
  "segment.meanshift": { dice: 0.8714, iou: 0.7721, recall: 0.8948, precision: 0.8493 },
  "segment.chan_vese": { dice: 0.8541, iou: 0.7453, recall: 0.8802, precision: 0.8297 },
  "segment.watershed": { dice: 0.8402, iou: 0.7245, recall: 0.8659, precision: 0.8162 },
  "segment.threshold": { dice: 0.7903, iou: 0.6532, recall: 0.8341, precision: 0.7511 },
  "dl.unet_endoscopie": { dice: 0.9035, iou: 0.8242, recall: 0.9287, precision: 0.8794 },
  "dl.unet_busi": { dice: 0.8962, iou: 0.8119, recall: 0.9203, precision: 0.8731 },
};

function lastSegment(steps: Step[]): string {
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    if (steps[index].kind.startsWith("segment.") || steps[index].kind.startsWith("dl.")) {
      return steps[index].kind;
    }
  }
  return "segment.otsu";
}

function scoresFor(steps: Step[]) {
  return SEGMENT_SCORES[lastSegment(steps)] ?? SEGMENT_SCORES["segment.otsu"];
}

function stepDuration(kind: string): number {
  return BASE_MS[kind] ?? 6;
}

let assetSeq = 3;
let analysisSeq = 4;
const objectUrls = new Map<string, string>();

const assets: Asset[] = [
  {
    id: "asset-442",
    kind: "image",
    filename: "frame442.png",
    width: 640,
    height: 480,
    channels: 3,
    bytes: 348268,
    created_at: "2026-10-30T09:12:00Z",
    meta: { dtype: "uint8", mean: 96.4, min: 0, max: 255 },
  },
  {
    id: "asset-442-mask",
    kind: "mask",
    filename: "frame442_glottis.png",
    width: 640,
    height: 480,
    channels: 1,
    bytes: 1087,
    created_at: "2026-10-30T09:12:00Z",
    meta: { dtype: "uint8", min: 0, max: 255, mask_fraction: 0.0332 },
  },
];

const demoParts: DemoPart[] = [
  { name: "image", kind: "image", url: DEMO_IMAGE, width: 640, height: 480 },
  { name: "mask", kind: "mask", url: DEMO_MASK, width: 640, height: 480 },
];

const demos: Demo[] = [
  {
    slug: "endoscopie-cours",
    label: {
      fr: "Endoscopie laryngée, glotte annotée",
      en: "Laryngeal endoscopy, annotated glottis",
    },
    description: {
      fr: "Image du cours avec le contour de la glotte comme masque de référence.",
      en: "Course image with the glottis outline as reference mask.",
    },
    kind: "image",
    width: 640,
    height: 480,
    has_reference_mask: true,
    parts: demoParts,
    landmarks: null,
  },
  {
    slug: "endoscopie-unet",
    label: { fr: "Endoscopie, prédiction U-Net", en: "Endoscopy, U-Net prediction" },
    description: {
      fr: "Même image, réseau U-Net entraîné sur l'endoscopie.",
      en: "Same image, U-Net trained on endoscopy.",
    },
    kind: "image",
    width: 640,
    height: 480,
    has_reference_mask: true,
    parts: demoParts,
    landmarks: null,
  },
];

const presets: Preset[] = [
  {
    slug: "otsu",
    label_fr: "Seuillage d'Otsu",
    label_en: "Otsu threshold",
    expected_dice: 0.9,
    asset_hint: "endoscopie-cours",
    steps: [
      { kind: "preprocess.gray", params: {} },
      { kind: "preprocess.median", params: { ksize: 5 } },
      { kind: "segment.otsu", params: { invert: false } },
      { kind: "postprocess.open", params: { ksize: 3 } },
      { kind: "postprocess.largest_component", params: {} },
    ],
  },
  {
    slug: "kmeans",
    label_fr: "k-means puis ouverture",
    label_en: "k-means then opening",
    expected_dice: 0.44,
    asset_hint: "endoscopie-cours",
    steps: [
      { kind: "preprocess.gray", params: {} },
      { kind: "segment.kmeans", params: { k: 3, seed: 42 } },
      { kind: "postprocess.open", params: { ksize: 3 } },
      { kind: "postprocess.largest_component", params: {} },
    ],
  },
  {
    slug: "watershed",
    label_fr: "Watershed",
    label_en: "Watershed",
    expected_dice: 0.9,
    asset_hint: "endoscopie-cours",
    steps: [
      { kind: "preprocess.gray", params: {} },
      { kind: "segment.watershed", params: { threshold_ratio: 0.5 } },
      { kind: "postprocess.largest_component", params: {} },
    ],
  },
  {
    slug: "chan-vese",
    label_fr: "Level-set Chan-Vese",
    label_en: "Chan-Vese level set",
    expected_dice: 0.85,
    asset_hint: "endoscopie-cours",
    steps: [
      { kind: "preprocess.gray", params: {} },
      { kind: "preprocess.clahe", params: { clip: 2, grid: 8 } },
      { kind: "segment.chan_vese", params: { iterations: 50, smoothing: 1, crop: true } },
    ],
  },
  {
    slug: "unet",
    label_fr: "U-Net endoscopie",
    label_en: "U-Net endoscopy",
    expected_dice: 0.96,
    asset_hint: "endoscopie-unet",
    steps: [
      { kind: "preprocess.gray", params: {} },
      { kind: "dl.unet_endoscopie", params: { threshold: 0.5 } },
    ],
  },
];


function seedAnalysis(
  id: string,
  steps: Step[],
  created: string,
  status: AnalysisStatus = "done",
): Analysis {
  const scores = scoresFor(steps);
  const total = steps.reduce((sum, step) => sum + stepDuration(step.kind), 0);
  return {
    id,
    asset_id: "asset-442",
    reference_mask_id: "asset-442-mask",
    steps,
    status,
    progress: status === "done" ? 1 : 0,
    created_at: created,
    finished_at: status === "done" ? created : null,
    error: null,
    summary:
      status === "done"
        ? { ...scores, total_ms: total }
        : null,
  };
}

const registrations: Registration[] = [];

const analyses: Analysis[] = [
  seedAnalysis(
    "an-01",
    [
      { kind: "preprocess.gray", params: {} },
      { kind: "preprocess.median", params: { ksize: 5 } },
      { kind: "segment.otsu", params: { invert: false } },
      { kind: "postprocess.open", params: { ksize: 3 } },
    ],
    "2026-10-30T09:14:10Z",
  ),
  seedAnalysis(
    "an-02",
    [
      { kind: "preprocess.gray", params: {} },
      { kind: "preprocess.clahe", params: { clip: 2, grid: 8 } },
      { kind: "segment.meanshift", params: { subsample: 3, fov_restrict: true } },
      { kind: "postprocess.largest_component", params: {} },
    ],
    "2026-10-30T09:18:42Z",
  ),
  seedAnalysis(
    "an-03",
    [
      { kind: "preprocess.gray", params: {} },
      { kind: "dl.unet_endoscopie", params: { threshold: 0.5 } },
    ],
    "2026-10-30T09:22:05Z",
  ),
];

function delay(ms: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, ms);
  return promise;
}

function nowIso(): string {
  return new Date().toISOString();
}

function find<T extends { id: string }>(list: T[], id: string): T {
  const item = list.find((entry) => entry.id === id);
  if (!item) throw new ApiError("asset_not_found", 404);
  return item;
}

function resultFor(analysis: Analysis): AnalysisResult {
  const scores = scoresFor(analysis.steps);
  const steps: StepResult[] = analysis.steps.map((step, index) => ({
    kind: step.kind,
    params: step.params,
    duration_ms: stepDuration(step.kind) + index,
    diagnostics:
      step.kind === "segment.otsu"
        ? { threshold: 118, mask_pixels: 10201 }
        : step.kind.startsWith("segment.")
          ? { mask_pixels: 10201 }
          : undefined,
  }));
  return {
    analysis_id: analysis.id,
    mask_url: DEMO_MASK,
    overlay_url: DEMO_MASK,
    diagnostics: {
      threshold: 118,
      mask_pixels: 10201,
      reference_pixels: 10201,
      mask_fraction: 0.0332,
    },
    metrics: { ...scores },
    steps,
    total_ms: steps.reduce((sum, step) => sum + step.duration_ms, 0),
  };
}

const listeners = new Map<string, Set<(event: StepProgressEvent) => void>>();

function emit(id: string, event: StepProgressEvent) {
  listeners.get(id)?.forEach((listener) => listener(event));
}

function runSimulation(analysis: Analysis) {
  analysis.status = "running";
  analysis.progress = 0;
  const total = Math.min(2600, 420 + analysis.steps.length * 320);
  const started = Date.now();
  const timer = setInterval(() => {
    const ratio = Math.min(1, (Date.now() - started) / total);
    analysis.progress = Math.round(ratio * 100) / 100;
    const stepIndex = Math.min(
      analysis.steps.length - 1,
      Math.floor(ratio * analysis.steps.length),
    );
    emit(analysis.id, {
      id: analysis.id,
      status: "running",
      progress: analysis.progress,
      message: analysis.steps[stepIndex]?.kind,
    });
    if (ratio >= 1) {
      clearInterval(timer);
      analysis.status = "done";
      analysis.progress = 1;
      analysis.finished_at = nowIso();
      const result = resultFor(analysis);
      analysis.summary = {
        dice: result.metrics?.dice ?? undefined,
        iou: result.metrics?.iou ?? undefined,
        recall: result.metrics?.recall ?? undefined,
        precision: result.metrics?.precision ?? undefined,
        total_ms: result.total_ms,
      };
      emit(analysis.id, { id: analysis.id, status: "done", progress: 1 });
    }
  }, 160);
}

export const mockApi = {
  mode: "demo" as const,

  async health(): Promise<Health> {
    await delay(40);
    return { status: "ok", version: "0.1.0-demo", models: { endoscopie: true, busi: true } };
  },

  async listDemos(): Promise<Demo[]> {
    await delay(60);
    return demos.map((demo) => ({ ...demo }));
  },

  async listAssets(): Promise<Asset[]> {
    await delay(60);
    return assets.map((asset) => ({ ...asset }));
  },

  assetFileUrl(id: string): string {
    const asset = find(assets, id);
    if (asset.kind === "mask") return DEMO_MASK;
    return objectUrls.get(id) ?? DEMO_IMAGE;
  },

  async createAssetFromDemo(slug: string, part = "image"): Promise<Asset> {
    await delay(120);
    const demo = demos.find((entry) => entry.slug === slug);
    if (!demo) throw new ApiError("asset_not_found", 404);
    const filename = `${demo.slug}-${part}.png`;
    const existing = assets.find((asset) => asset.filename === filename);
    if (existing) return { ...existing };
    const isMask = part === "mask";
    const asset: Asset = {
      id: `asset-${assetSeq++}`,
      kind: isMask ? "mask" : "image",
      filename,
      width: demo.width,
      height: demo.height,
      channels: isMask ? 1 : 3,
      bytes: isMask ? 1087 : 348268,
      created_at: nowIso(),
      meta: isMask ? { mask_fraction: 0.0332 } : { dtype: "uint8" },
    };
    assets.push(asset);
    return { ...asset };
  },

  async uploadAsset(file: File, kind: Asset["kind"]): Promise<Asset> {
    await delay(220);
    const allowed = ["image/png", "image/jpeg", "image/tiff", "image/bmp"];
    if (!allowed.includes(file.type)) {
      throw new ApiError("unsupported_type", 415);
    }
    if (file.size > 25 * 1024 * 1024) {
      throw new ApiError("asset_too_large", 413, { bytes: file.size });
    }
    const dimensions = await readImageSize(file);
    const id = `asset-${assetSeq++}`;
    if (typeof URL !== "undefined" && URL.createObjectURL) {
      objectUrls.set(id, URL.createObjectURL(file));
    }
    const asset: Asset = {
      id,
      kind,
      filename: file.name,
      width: dimensions.width,
      height: dimensions.height,
      channels: 3,
      bytes: file.size,
      created_at: nowIso(),
      meta: { dtype: "uint8" },
    };
    assets.push(asset);
    return { ...asset };
  },

  async deleteAsset(id: string): Promise<void> {
    await delay(80);
    const index = assets.findIndex((asset) => asset.id === id);
    if (index >= 0) assets.splice(index, 1);
    const url = objectUrls.get(id);
    if (url) {
      URL.revokeObjectURL(url);
      objectUrls.delete(id);
    }
  },

  async pipelineSchema(): Promise<PipelineSchema> {
    await delay(30);
    return PIPELINE_SCHEMA;
  },

  async getPresets(): Promise<Preset[]> {
    await delay(40);
    return presets.map((preset) => ({ ...preset, steps: preset.steps.map((step) => ({ ...step })) }));
  },

  async createRegistration(input: {
    fixed_asset_id: string;
    moving_asset_id: string;
    method: Registration["method"];
  }): Promise<Registration> {
    await delay(900);
    const registration: Registration = {
      id: `reg-${registrations.length + 1}`,
      fixed_asset_id: input.fixed_asset_id,
      moving_asset_id: input.moving_asset_id,
      method: input.method,
      status: "done",
      progress: 1,
      metrics: { ncc: 0.9418, mse: 286.4, nmi: 0.3512, confidence: 0.64 },
      transform: [
        [1.0241, 0.0672, -44.49],
        [-0.0568, 1.0141, 20.13],
        [0.0000139, 0.0000081, 1],
      ],
      overlay_url: DEMO_IMAGE,
      checkerboard_url: DEMO_IMAGE,
    };
    registrations.push(registration);
    return { ...registration };
  },

  async getRegistration(id: string): Promise<Registration> {
    await delay(40);
    return { ...find(registrations, id) };
  },

  async submitLandmarks(id: string, points: number[][]): Promise<Registration> {
    await delay(120);
    const registration = find(registrations, id);
    registration.metrics = {
      ...registration.metrics,
      mean_landmark_error: 2.86,
      success_rate: points.length ? 100 : null,
    };
    return { ...registration };
  },

  async createAnalysis(input: {
    asset_id: string;
    reference_mask_id?: string | null;
    steps: Step[];
  }): Promise<Analysis> {
    await delay(120);
    find(assets, input.asset_id);
    if (!input.steps.length) throw new ApiError("pipeline_invalid", 422);
    const analysis: Analysis = {
      id: `an-${String(analysisSeq++).padStart(2, "0")}`,
      asset_id: input.asset_id,
      reference_mask_id: input.reference_mask_id ?? null,
      steps: input.steps.map((step) => ({ ...step, params: { ...step.params } })),
      status: "queued",
      progress: 0,
      created_at: nowIso(),
      finished_at: null,
      error: null,
      summary: null,
    };
    analyses.unshift(analysis);
    runSimulation(analysis);
    return { ...analysis };
  },

  async listAnalyses(): Promise<Analysis[]> {
    await delay(40);
    return analyses.slice(0, 50).map((analysis) => ({ ...analysis }));
  },

  async getAnalysis(id: string): Promise<Analysis> {
    await delay(40);
    return { ...find(analyses, id) };
  },

  async getResult(id: string): Promise<AnalysisResult> {
    await delay(60);
    const analysis = find(analyses, id);
    if (analysis.status !== "done") throw new ApiError("step_failed", 404);
    return resultFor(analysis);
  },

  async deleteAnalysis(id: string): Promise<void> {
    await delay(60);
    const index = analyses.findIndex((analysis) => analysis.id === id);
    if (index >= 0) analyses.splice(index, 1);
  },

  watchAnalysis(id: string, onEvent: (event: StepProgressEvent) => void): () => void {
    const set = listeners.get(id) ?? new Set();
    set.add(onEvent);
    listeners.set(id, set);
    return () => {
      set.delete(onEvent);
      if (!set.size) listeners.delete(id);
    };
  },
};

function readImageSize(file: File): Promise<{ width: number; height: number }> {
  const { promise, resolve } = Promise.withResolvers<{ width: number; height: number }>();
  if (typeof createImageBitmap !== "function") {
    resolve({ width: 0, height: 0 });
    return promise;
  }
  createImageBitmap(file)
    .then((bitmap) => {
      resolve({ width: bitmap.width, height: bitmap.height });
      bitmap.close();
    })
    .catch(() => resolve({ width: 0, height: 0 }));
  return promise;
}

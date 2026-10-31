// Single network module. Every call goes through here.
import { mockApi } from "./mock";
import {
  ApiError,
  type Analysis,
  type AnalysisResult,
  type Asset,
  type AssetKind,
  type Demo,
  type ErrorCode,
  type Health,
  type PipelineSchema,
  type PipelineStepSpec,
  type Preset,
  type Registration,
  type RegistrationMethod,
  type Step,
  type StepProgressEvent,
} from "./types";

const hasApiOrigin = (process.env.NEXT_PUBLIC_API_URL ?? "").length > 0;
export const isDemoMode = !hasApiOrigin;
// Browser calls go through the Next proxy: same-origin cookies, no canvas taint.
const BASE_URL = isDemoMode ? "" : "/lum-api";

export interface LumenApi {
  mode: "demo" | "live";
  health(): Promise<Health>;
  listDemos(): Promise<Demo[]>;
  listAssets(): Promise<Asset[]>;
  assetFileUrl(id: string): string;
  createAssetFromDemo(slug: string, part?: string): Promise<Asset>;
  uploadAsset(file: File, kind: AssetKind): Promise<Asset>;
  deleteAsset(id: string): Promise<void>;
  pipelineSchema(): Promise<PipelineSchema>;
  getPresets(): Promise<Preset[]>;
  createAnalysis(input: {
    asset_id: string;
    reference_mask_id?: string | null;
    steps: Step[];
  }): Promise<Analysis>;
  listAnalyses(): Promise<Analysis[]>;
  getAnalysis(id: string): Promise<Analysis>;
  getResult(id: string): Promise<AnalysisResult>;
  deleteAnalysis(id: string): Promise<void>;
  watchAnalysis(id: string, onEvent: (event: StepProgressEvent) => void): () => void;
  createRegistration(input: {
    fixed_asset_id: string;
    moving_asset_id: string;
    method: RegistrationMethod;
    params?: Record<string, unknown>;
  }): Promise<Registration>;
  getRegistration(id: string): Promise<Registration>;
  submitLandmarks(id: string, points: number[][]): Promise<Registration>;
}

const KNOWN_CODES: ErrorCode[] = [
  "asset_too_large",
  "unsupported_type",
  "asset_not_found",
  "pipeline_invalid",
  "step_failed",
  "model_missing",
  "registration_failed",
  "landmarks_invalid",
  "network",
  "unknown",
];

export function resolveApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  // API paths already carry /api; the proxy adds it again on its side.
  const clean = path.replace(/^\/api(?=\/|$)/, "");
  return `${BASE_URL}${clean.startsWith("/") ? "" : "/"}${clean}`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    const headers = new Headers(init.headers);
    if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    response = await fetch(`${BASE_URL}${path}`, {
      credentials: "include",
      ...init,
      headers,
    });
  } catch {
    throw new ApiError("network", 0);
  }

  if (!response.ok) {
    let code: ErrorCode = "unknown";
    let details: Record<string, unknown> | undefined;
    try {
      const payload = (await response.json()) as {
        error?: { code?: string; details?: Record<string, unknown> };
      };
      const raw = payload.error?.code;
      if (raw && (KNOWN_CODES as string[]).includes(raw)) code = raw as ErrorCode;
      details = payload.error?.details;
    } catch {
      // Response body is not the documented error envelope.
    }
    throw new ApiError(code, response.status, details);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

type RawParam = {
  type?: string;
  minimum?: number;
  maximum?: number;
  default?: number | boolean;
  key?: string;
};

type RawStep = {
  kind?: string;
  group?: string;
  params?: RawParam[] | Record<string, RawParam>;
  title?: string;
  properties?: {
    kind?: { const?: string };
    params?: { properties?: Record<string, RawParam> };
  };
};

function toSpecs(params: RawParam[] | Record<string, RawParam> | undefined): PipelineStepSpec["params"] {
  const specs: PipelineStepSpec["params"] = [];
  if (!params) return specs;
  const entries: [string, RawParam][] = Array.isArray(params)
    ? params.filter((param) => param.key).map((param) => [param.key as string, param])
    : Object.entries(params);
  for (const [key, param] of entries) {
    specs.push({
      key,
      type: param.type === "boolean" ? "boolean" : param.type === "number" ? "number" : "integer",
      minimum: param.minimum,
      maximum: param.maximum,
      default: param.default ?? 0,
    });
  }
  return specs;
}

// Accepts the exported JSON Schema and the flat catalogue shape.
function normalizeSchema(raw: unknown): PipelineSchema {
  const root = raw as {
    steps?: unknown;
    properties?: { steps?: { items?: { oneOf?: RawStep[] } } };
  };
  const container = root.steps ?? root.properties?.steps?.items?.oneOf;
  const entries: RawStep[] = [];

  if (Array.isArray(container)) {
    entries.push(...(container as RawStep[]));
  } else if (container && typeof container === "object") {
    for (const [kind, value] of Object.entries(container as Record<string, unknown>)) {
      const entry = value as { group?: string; properties?: Record<string, RawParam> };
      entries.push({ kind, group: entry.group, params: entry.properties });
    }
  }

  const steps: PipelineStepSpec[] = [];
  for (const entry of entries) {
    const kind = entry.kind ?? entry.properties?.kind?.const;
    if (!kind) continue;
    const params = entry.params ?? entry.properties?.params?.properties;
    steps.push({
      kind,
      group: entry.group ?? kind.split(".")[0],
      params: toSpecs(params),
    });
  }
  return { steps };
}

// Mask, overlay and checkerboard paths are relative to the API origin.
function withResolvedDataUrls(registration: Registration): Registration {
  return {
    ...registration,
    overlay_url: registration.overlay_url ? resolveApiUrl(registration.overlay_url) : null,
    checkerboard_url: registration.checkerboard_url
      ? resolveApiUrl(registration.checkerboard_url)
      : null,
  };
}

const liveApi: LumenApi = {
  mode: "live",

  health: () => request<Health>("/health"),

  listDemos: () => request<Demo[]>("/demos"),

  listAssets: () => request<Asset[]>("/assets"),

  assetFileUrl(id: string) {
    return resolveApiUrl(`/assets/${id}/file`);
  },

  createAssetFromDemo: (slug: string, part = "image") =>
    request<Asset>(`/demos/${encodeURIComponent(slug)}/asset?part=${encodeURIComponent(part)}`, {
      method: "POST",
    }),

  uploadAsset: (file: File, kind: AssetKind) => {
    const body = new FormData();
    body.append("file", file);
    body.append("kind", kind);
    return request<Asset>("/assets", { method: "POST", body });
  },

  deleteAsset: (id: string) => request<void>(`/assets/${id}`, { method: "DELETE" }),

  async pipelineSchema() {
    const raw = await request<unknown>("/schema/pipeline");
    return normalizeSchema(raw);
  },

  async getPresets() {
    try {
      const raw = await request<Preset[] | { presets?: Preset[] }>("/presets");
      const list = Array.isArray(raw) ? raw : raw.presets ?? [];
      return list.map((preset) => {
        const legacy = preset as Preset & {
          id?: string;
          expected?: { dice?: number };
        };
        return {
          ...preset,
          slug: preset.slug ?? legacy.id ?? preset.label_en,
          steps: preset.steps ?? [],
          expected_dice: preset.expected_dice ?? legacy.expected?.dice ?? null,
          asset_hint: preset.asset_hint ?? null,
        };
      });
    } catch {
      // Route absent until the preset package ships: section stays hidden.
      return [];
    }
  },

  createAnalysis: (input) =>
    request<Analysis>("/analyses", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  listAnalyses: () => request<Analysis[]>("/analyses"),

  getAnalysis: (id: string) => request<Analysis>(`/analyses/${id}`),

  async getResult(id: string) {
    const result = await request<AnalysisResult>(`/analyses/${id}/result`);
    return {
      ...result,
      mask_url: resolveApiUrl(result.mask_url),
      overlay_url: resolveApiUrl(result.overlay_url),
    };
  },

  deleteAnalysis: (id: string) => request<void>(`/analyses/${id}`, { method: "DELETE" }),

  // Polling is enough at 800 ms and survives cross-origin cookies.
  watchAnalysis(id: string, onEvent: (event: StepProgressEvent) => void) {
    let stopped = false;
    let timer = 0;
    const tick = async () => {
      try {
        const analysis = await request<Analysis>(`/analyses/${id}`);
        onEvent({ id, status: analysis.status, progress: analysis.progress });
        if (analysis.status === "done" || analysis.status === "error") return;
      } catch {
        // Transient network error: keep polling.
      }
      if (!stopped) timer = window.setTimeout(tick, 800);
    };
    timer = window.setTimeout(tick, 300);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  },

  async createRegistration(input) {
    const registration = await request<Registration>("/registrations", {
      method: "POST",
      body: JSON.stringify(input),
    });
    return withResolvedDataUrls(registration);
  },

  async getRegistration(id: string) {
    return withResolvedDataUrls(await request<Registration>(`/registrations/${id}`));
  },

  async submitLandmarks(id, points) {
    const registration = await request<Registration>(`/registrations/${id}/landmarks`, {
      method: "POST",
      body: JSON.stringify({ points }),
    });
    return withResolvedDataUrls(registration);
  },
};

export const api: LumenApi = isDemoMode ? mockApi : liveApi;

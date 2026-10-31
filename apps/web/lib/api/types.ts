// Types hand-written from docs/CONTRACT.md until packages/contracts/openapi.json
// is exported by the API package.

export type AssetKind = "image" | "mask";

export type Asset = {
  id: string;
  kind: AssetKind;
  filename: string;
  width: number;
  height: number;
  channels: number;
  bytes: number;
  created_at: string;
  meta?: {
    dtype?: string;
    mean?: number;
    min?: number;
    max?: number;
    mask_fraction?: number;
  };
};

export type Localized = { fr: string; en: string };

export type DemoPart = {
  name: string;
  kind: AssetKind;
  url: string;
  width: number;
  height: number;
};

export type Demo = {
  slug: string;
  label: Localized;
  description: Localized;
  kind: AssetKind;
  width: number;
  height: number;
  has_reference_mask: boolean;
  parts: DemoPart[];
  landmarks: number[][] | null;
};

export type Preset = {
  slug: string;
  label_fr: string;
  label_en: string;
  description_fr?: string;
  description_en?: string;
  expected_dice: number | null;
  asset_hint: string | null;
  steps: Step[];
};

export type Step = {
  kind: string;
  params: Record<string, unknown>;
};

export type AnalysisStatus = "queued" | "running" | "done" | "error";

export type AnalysisSummary = {
  dice?: number;
  iou?: number;
  recall?: number;
  precision?: number;
  total_ms?: number;
};

export type Analysis = {
  id: string;
  asset_id: string;
  reference_mask_id: string | null;
  steps: Step[];
  status: AnalysisStatus;
  progress: number;
  created_at: string;
  finished_at: string | null;
  error: string | null;
  summary: AnalysisSummary | null;
};

export type StepMetrics = {
  dice: number | null;
  iou: number | null;
  recall: number | null;
  precision: number | null;
};

export type StepResult = {
  kind: string;
  params: Record<string, unknown>;
  duration_ms: number;
  diagnostics?: Record<string, unknown>;
};

export type AnalysisResult = {
  analysis_id: string;
  mask_url: string;
  overlay_url: string;
  diagnostics: Record<string, unknown>;
  metrics: StepMetrics | null;
  steps: StepResult[];
  total_ms: number;
};

export type RegistrationMethod = "translation" | "affine" | "homography" | "optical_flow";

export type RegistrationMetrics = {
  mean_landmark_error?: number | null;
  success_rate?: number | null;
  ncc?: number | null;
  mse?: number | null;
  nmi?: number | null;
  confidence?: number | null;
};

export type Registration = {
  id: string;
  fixed_asset_id: string;
  moving_asset_id: string;
  method: RegistrationMethod;
  status: AnalysisStatus;
  progress?: number;
  metrics: RegistrationMetrics | null;
  transform: number[][] | null;
  overlay_url: string | null;
  checkerboard_url: string | null;
  created_at?: string;
  finished_at?: string | null;
  error?: string | null;
};

export type Health = {
  status: "ok";
  version: string;
  models: { endoscopie: boolean; busi: boolean };
};

export type PipelineParamSpec = {
  key: string;
  type: "integer" | "number" | "boolean";
  minimum?: number;
  maximum?: number;
  default: number | boolean;
};

export type PipelineStepSpec = {
  kind: string;
  group: string;
  params: PipelineParamSpec[];
};

export type PipelineSchema = {
  steps: PipelineStepSpec[];
};

export type StepProgressEvent = {
  id: string;
  status: AnalysisStatus;
  progress: number;
  message?: string;
};

export type ErrorCode =
  | "asset_too_large"
  | "unsupported_type"
  | "asset_not_found"
  | "pipeline_invalid"
  | "step_failed"
  | "model_missing"
  | "registration_failed"
  | "landmarks_invalid"
  | "network"
  | "unknown";

export class ApiError extends Error {
  code: ErrorCode;
  details?: Record<string, unknown>;
  status: number;

  constructor(code: ErrorCode, status = 0, details?: Record<string, unknown>) {
    super(code);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

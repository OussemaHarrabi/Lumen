import type { PipelineStepSpec } from "./types";

// Default parameters for a step, straight from its catalogue entry.
export function defaultParams(spec: PipelineStepSpec): Record<string, unknown> {
  const params: Record<string, unknown> = {};
  for (const param of spec.params) {
    params[param.key] = param.default;
  }
  return params;
}

export interface OrbitalObject {
  catalog_id: string;
  position_km: number[];
  velocity_kms: number[];
  altitude_km: number;
  hbr_m: number;
  met_criteria: boolean;
  cov_max_eigenvalue_km2: number | null;
}

export interface ConjunctionEvent {
  event_id: string;
  conj_id: string;
  source: string;
  stratum: string;
  tca: string;
  miss_distance_km: number;
  relative_speed_kms: number;
  mahalanobis_distance: number | null;
  dilution: number | null;
  pc: number | null;
  pc_is_floored: boolean;
  objects: [OrbitalObject, OrbitalObject];
}

export interface HealthCheck {
  ok: boolean;
  files?: string[];
  sources?: Record<string, number>;
  [key: string]: unknown;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  checks: { sgp4: HealthCheck; tracss_store: HealthCheck; kelvins_store: HealthCheck; llm: HealthCheck };
  provenance: Record<string, unknown>;
}

export interface ConditioningBlock {
  was_conditioned: boolean;
  had_negative_eigenvalue: boolean;
  condition_number: number;
  smallest_original_eigenvalue: number;
  method: string;
}

export interface PcResult {
  pc: number;
  log10_pc: number | null;
  miss_distance_km: number;
  relative_speed_kms: number;
  combined_hard_body_radius_m: number;
  mahalanobis_distance_2d: number;
  mahalanobis_distance_3d: number;
  projected_covariance_km2: number[][];
  conditioning_2d: ConditioningBlock;
  conditioning_3d: ConditioningBlock;
  provenance: Record<string, unknown>;
}

export interface TriageVerdict {
  series_id: string;
  in_scope: boolean;
  baseline_risk: number;
  predicted_final_risk?: number | null;
  effective_prediction: number;
  will_collapse?: boolean | null;
  confidence?: string | null;
  reasoning?: string | null;
  evidence_cited: { field: string; value: unknown }[];
  error?: string | null;
}

export interface TriagePayload {
  recorded?: boolean;
  verdicts: TriageVerdict[];
  requested: number;
  answered: number;
  failed: number;
  provenance: Record<string, unknown>;
}

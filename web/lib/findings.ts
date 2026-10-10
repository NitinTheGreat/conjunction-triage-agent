/** Types and helpers for /data/paper_findings.json (written by research/web_findings.py). */

export type ConditionKey = "no_reuse" | "overlap_50" | "overlap_90" | "solution_reissue" | "new_information";

export type Condition = {
  key: ConditionKey; label: string; note: string; windows: number[][];
  message_observation_pairs: number; unique_observations: number;
};

export type Decision = {
  id: string; role: string; arm: string; comparator: string; condition: string; estimand: string;
  mean: number; lower: number; upper: number; scenario_lower: number; scenario_upper: number;
  null: number | null; p_value: number | null; holm_rejected: boolean | null; decision: string | null;
};

export type LossSummary = { arm: string; condition: string; mean: number; min: number; max: number; missed: number; positives: number };
export type Rate = { arm: string; condition: string; miss_rate: number; review_fraction: number; roc_auc: number };
export type BankValue = { bank: string; mean: number };
export type DevelopmentBank = { configuration: string; key: string; bank: string; mean: number; lower: number; upper: number };
export type RealContrast = {
  split: string; id: string; arm: string; comparator: string; mean: number; event_lower: number; event_upper: number;
  mission_lower: number; mission_upper: number; missions: number; events: number; positives: number;
};
export type RealMetric = { split: string; arm: string; n: number; positives: number; log_loss: number; roc_auc: number; reviewed_95: number; missed_95: number };
export type RegisterRow = { id: string; evidence_type: string; claim: string; value: number };

export type Findings = {
  protocol: {
    sha256: string; git_head_at_freeze: string; frozen_utc: string; claim: string;
    configuration: { eigenvalues: number[]; rotation_degrees: number; note: string };
    training_banks: number; training_scenarios: number; evaluation_scenarios: number; margin: number;
    bootstrap_resamples: number; label: string; population: string; pinned_files: number;
  };
  design: {
    observations_total: number; observations_visible: number; availability_days: number[];
    message_times_days: number[]; replay_note: string; conditions: Condition[];
  };
  scientific: {
    decisions: Decision[]; losses: LossSummary[]; rates: Rate[]; banks: Record<string, BankValue[]>;
    misses: { new: number; recovered: number; positives: number };
    selections: { models: number; at_upper_C: number; max_iterations: number };
    labelled_rows: number; bank_sd: number;
  };
  development: { p1_banks: DevelopmentBank[]; bias_transfer_mean: number };
  real: {
    contrasts: RealContrast[]; metrics: RealMetric[];
    frontiers: Record<string, Record<string, [number, number][]>>;
    cohort: Record<"train" | "test", { raw_events: number; eligible_events: number; positives: number }>;
  };
  arms: Record<string, string>;
  register: RegisterRow[];
  inputs_sha256: Record<string, string>;
};

/** Validated with the dataviz checks: rust/blue pass CVD and contrast on paper, cream and the dark panel. */
export const palette = {
  reused: "#b45436", fresh: "#2f6fa3", context: "#9b9686",
  reusedDark: "#d35c3d", freshDark: "#4b88c4", idleDark: "#7a7c6a", acid: "#d0d68b",
  ink: "#29261f", muted: "#726e60", grid: "#d6d1c4", axis: "#b9b4a5",
};

export const fixed = (value: number, places = 3) => (value < 0 ? "−" : "") + Math.abs(value).toFixed(places);
export const signed = (value: number, places = 3) => (value < 0 ? "−" : "+") + Math.abs(value).toFixed(places);
export const percent = (value: number, places = 1) => `${(value * 100).toFixed(places)}%`;
export const count = (value: number) => value.toLocaleString("en-US");

export function registerId(data: Findings, matches: (row: RegisterRow) => boolean) {
  return data.register.find(matches)?.id ?? null;
}

/** Message k's observations that some earlier message already used. */
export function reusedIn(windows: number[][], message: number) {
  const earlier = new Set(windows.slice(0, message).flat());
  return windows[message].filter((id) => earlier.has(id));
}

export function messagesUsing(windows: number[][], observation: number) {
  return windows.flatMap((window, index) => window.includes(observation) ? [index] : []);
}

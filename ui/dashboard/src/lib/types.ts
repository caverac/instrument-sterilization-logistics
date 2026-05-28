/** Shared types used across the dashboard. */

export type FacilityId = 'BOCA' | 'LGB' | 'ELM'

/** The three routing policies we compare. */
export type PolicyId = 'mean-only' | 'proximity' | 'variance-aware'

/** Request body for POST /decide. Mirrors the routing service's DecideRequest. */
export interface DecideRequest {
  tray_type_id: string
  hour_of_pickup: number
  deadline_min: number
  client_id: string
}

/** One per-facility cell in the response. */
export interface FacilityCell {
  facility_id: string
  name: string
  profile: string
  expected_completion_min: number
  p_on_time: number
}

/** One policy's choice + diagnostic scores. */
export interface PolicyDecision {
  policy_id: PolicyId
  facility_id: string
  score: number | null
  score_metric: string | null
  candidate_scores: Record<string, number>
}

/** Response body for POST /decide. */
export interface DecideResponse {
  facilities: FacilityCell[]
  policies: PolicyDecision[]
}

/** Tray-type options exposed in the Explorer UI. Must match the IDs the model
 *  was trained on (synth-events' TRAY_TYPES). */
export const TRAY_TYPES: ReadonlyArray<{ id: string; label: string }> = [
  { id: 'TRAY-SMALL', label: 'Small instrument' },
  { id: 'TRAY-KNEE', label: 'Knee arthroscopy' },
  { id: 'TRAY-LAPS', label: 'Laparoscopic' },
  { id: 'TRAY-CARDIO', label: 'Cardiac major' },
  { id: 'TRAY-SPINE', label: 'Spine instrumentation' }
]

/** Client options exposed in the Explorer UI. */
export const CLIENT_OPTIONS: ReadonlyArray<{ id: string; label: string }> = [
  { id: 'HOSPITAL_A', label: 'Hospital A' },
  { id: 'HOSPITAL_B', label: 'Hospital B' },
  { id: 'HOSPITAL_C', label: 'Hospital C' },
  { id: 'ASC_X', label: 'ASC X' },
  { id: 'ASC_Y', label: 'ASC Y' }
]

/** A row from the projector's `tray` table (current state of one tray). */
export interface TrayState {
  tray_id: string
  current_facility_id: string
  current_stage: string
  last_event_ts: string
  last_updated: string
}

export interface TrayStatesResponse {
  trays: TrayState[]
}

/** A row from the projector's `journey` table (one finalized pickup cycle). */
export interface Journey {
  journey_id: string
  tray_id: string
  facility_id: string
  tray_type_id: string
  client_id: string
  pickup_ts: string
  required_by_ts: string
  delivered_ts: string
  on_time: boolean
  delay_min: number
  decon_dwell_min: number
  inspection_dwell_min: number
  assembly_dwell_min: number
  sterilization_dwell_min: number
  packout_dwell_min: number
  transport_min: number
}

export interface RecentJourneysResponse {
  journeys: Journey[]
}

/** Per-policy aggregate from a single backtest run. */
export interface BacktestPolicySummary {
  policy_id: PolicyId
  on_time_rate: number
  mean_delay_min: number
  p95_delay_min: number
}

/** On-time-rate lift of one policy over another, with a 95% bootstrap CI in pp. */
export interface BacktestLift {
  policy_id: PolicyId
  vs: PolicyId
  point_pp: number
  ci_95_lo_pp: number
  ci_95_hi_pp: number
}

export interface BacktestSummaryResponse {
  n: number
  per_policy: BacktestPolicySummary[]
  lifts: BacktestLift[]
}

/** Posterior summary stats for one scalar model parameter. */
export interface ParameterSummary {
  name: string
  mean: number
  sd: number
  p5: number
  p50: number
  p95: number
}

export interface ModelSummaryResponse {
  n_samples: number
  facility_ids: string[]
  tray_type_ids: string[]
  parameters: ParameterSummary[]
}

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

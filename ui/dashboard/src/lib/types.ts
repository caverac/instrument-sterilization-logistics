/** Shared types used across the dashboard. */

export type FacilityId = 'BOCA' | 'LGB' | 'ELM'

export interface FacilitySummary {
  id: FacilityId
  name: string
  meanCompletionMin: number
  stdCompletionMin: number
  onTimeRate: number
  /** Short narrative describing the facility's reliability profile. */
  profile: string
}

/** The three routing policies we compare. */
export type PolicyId = 'mean-only' | 'proximity' | 'variance-aware'

export interface PolicyChoice {
  policy: PolicyId
  facility: FacilityId
  predictedOnTime: number
}

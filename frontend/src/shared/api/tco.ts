import { apiRequest } from './client'
import type { ProfilePayload } from './profile'

export interface TcoCalculatePayload {
  modification_id: number
  horizon_years: number
  profile: ProfilePayload
  options: {
    include_kasko: boolean
    discount_rate_pct: number
  }
}

export type TcoComponentCode =
  | 'depreciation'
  | 'fuel'
  | 'osago'
  | 'kasko'
  | 'transport_tax'
  | 'maintenance'
  | 'tyres'

export interface TcoYearlyPoint {
  year_index: number
  total_rub: number
  cumulative_rub?: number
  by_component?: Partial<Record<TcoComponentCode, number>>
}

export interface TcoCalculateResponse {
  purchase_price_rub: number
  total_tco_rub: number
  total_tco_per_km_rub: number
  predicted_resale_price_rub: number
  components: Record<
    TcoComponentCode,
    {
      total_rub: number
      share_pct: number
      details?: Record<string, unknown>
    }
  >
  yearly: TcoYearlyPoint[]
  meta: {
    scope_disclaimer_ru: string
    excluded_items_ru: string[]
    included_items_ru: string[]
  }
}

export interface RecommendationFiltersPayload {
  purchase_price_min_rub?: number
  purchase_price_max_rub?: number
  body_types: string[]
  drives: string[]
  fuel_types: string[]
  transmissions: string[]
  segments: string[]
  year_min?: number
  year_max?: number
  power_min_hp?: number
  power_max_hp?: number
}

export interface RecommendRequestPayload {
  profile: ProfilePayload
  horizon_years: number
  top_n: number
  filters: RecommendationFiltersPayload
  weights_preset: 'balanced' | 'cheapest' | 'family' | 'premium' | 'student' | 'business'
  include_kasko?: boolean
}

export interface RecommendItem {
  rank: number
  score: number
  is_pareto_optimal: boolean
  modification: {
    id: number
    make: string
    model: string
    generation: string
    trim_name: string | null
    year_from: number
    year_to: number | null
    body_type: string
    segment: string
    power_hp: number
    fuel_type: string
    transmission: string
    drive: string
    fuel_consumption_combined_l_100km: number
    msrp_new_rub: number
  }
  tco_total_rub: number
  explanation_ru: string
}

export interface RecommendResponse {
  items: RecommendItem[]
  total_candidates: number
  weights: Record<string, number>
  metrics: {
    ndcg_at_k: number | null
    diversity_at_k: number
    coverage_ratio: number
    stability_at_k: number
  }
  computed_at: string
}

export interface CompareRequestPayload {
  profile: ProfilePayload
  horizon_years: number
  include_kasko?: boolean
  modification_ids: number[]
}

export interface CompareResponse {
  items: Array<{
    modification: {
      id: number
      make: string
      model: string
      generation: string
      trim_name: string | null
      year_from: number
      year_to: number | null
      body_type: string
      segment: string
      power_hp: number
      fuel_type: string
      transmission: string
      drive: string
      fuel_consumption_combined_l_100km: number
      msrp_new_rub: number
    }
    total_tco_rub: number
    components_rub: Record<TcoComponentCode, number>
    yearly: TcoYearlyPoint[]
    delta_total_rub_vs_first: number
    delta_components_vs_first: Array<{
      component: TcoComponentCode
      delta_rub_vs_first: number
    }>
  }>
  computed_at: string
}

export const tcoApi = {
  calculate: (payload: TcoCalculatePayload) =>
    apiRequest<TcoCalculateResponse>('/api/tco/calculate', {
      method: 'POST',
      body: payload,
    }),
  recommend: (payload: RecommendRequestPayload) =>
    apiRequest<RecommendResponse>('/api/tco/recommend', {
      method: 'POST',
      body: payload,
    }),
  compare: (payload: CompareRequestPayload) =>
    apiRequest<CompareResponse>('/api/tco/compare', {
      method: 'POST',
      body: payload,
    }),
}

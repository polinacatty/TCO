import { apiRequest } from './client'

export interface ScenarioCreatePayload {
  name?: string
  modification_ids?: number[]
  modifications?: Array<{ modification_id: number }>
}

// Legacy compatibility types for non-routed pages.
export interface ScenarioProfilePayload {
  region_id: number
  annual_mileage_km: number
  driver_age: number
  driver_experience_years: number
  osago_unlimited_drivers: boolean
  use_dealer_service: boolean
  include_kasko: boolean
  weights_preset: 'balanced' | 'cheapest' | 'family' | 'premium' | 'student' | 'business'
}

export interface ScenarioModificationPayload {
  modification_id: number
  custom_purchase_price_rub?: number
  age_at_purchase_months?: number
}

export interface ScenarioSummary {
  id: string
  name: string
  modifications_count: number
  modification_ids: number[]
  created_at: string
}

export interface ScenarioListResponse {
  items: ScenarioSummary[]
  next_cursor: string | null
  has_more: boolean
}

export interface ScenarioCarResult {
  modification_id: number
  total_tco_rub: number
  custom_purchase_price_rub: number | null
  age_at_purchase_months: number
}

export interface ScenarioRead {
  id: string
  name: string
  modification_ids: number[]
  created_at: string
  horizon_years?: number
  profile?: ScenarioProfilePayload
  options?: {
    include_kasko: boolean
    discount_rate_pct: number
  }
  summary_total_tco_rub?: number
  cars?: ScenarioCarResult[]
  updated_at?: string
}

export interface ScenarioExistsResponse {
  exists: boolean
  comparison_id: string | null
}

export const scenariosApi = {
  list: (token: string | null, params?: { include_deleted?: boolean; limit?: number; cursor?: string | null }) => {
    const query = new URLSearchParams()
    if (params?.include_deleted) query.set('include_deleted', 'true')
    if (params?.limit) query.set('limit', String(params.limit))
    if (params?.cursor) query.set('cursor', params.cursor)
    const suffix = query.toString() ? `?${query.toString()}` : ''
    return apiRequest<ScenarioListResponse>(`/api/saved-comparisons${suffix}`, { accessToken: token })
  },
  get: (token: string | null, scenarioId: string) =>
    apiRequest<ScenarioRead>(`/api/saved-comparisons/${scenarioId}`, { accessToken: token }),
  exists: (token: string | null, modificationIds: number[]) => {
    const query = new URLSearchParams()
    for (const id of modificationIds) {
      query.append('modification_ids', String(id))
    }
    return apiRequest<ScenarioExistsResponse>(`/api/saved-comparisons/exists?${query.toString()}`, {
      accessToken: token,
    })
  },
  create: (token: string | null, payload: ScenarioCreatePayload, idempotencyKey: string) => {
    const modificationIds =
      payload.modification_ids ??
      payload.modifications?.map((item) => item.modification_id) ??
      []
    return apiRequest<ScenarioRead>('/api/saved-comparisons', {
      method: 'POST',
      body: {
        name: payload.name,
        modification_ids: modificationIds,
      },
      accessToken: token,
      headers: { 'Idempotency-Key': idempotencyKey },
    })
  },
  delete: (token: string | null, scenarioId: string) =>
    apiRequest<void>(`/api/saved-comparisons/${scenarioId}`, {
      method: 'DELETE',
      accessToken: token,
    }),
  update: (token: string | null, scenarioId: string, payload: ScenarioCreatePayload) =>
    apiRequest<ScenarioRead>(`/api/saved-comparisons/${scenarioId}`, {
      method: 'PUT',
      body: payload,
      accessToken: token,
    }),
  recalculate: (token: string | null, scenarioId: string) =>
    apiRequest<ScenarioRead>(`/api/saved-comparisons/${scenarioId}/recalculate`, {
      method: 'POST',
      accessToken: token,
    }),
}

import { apiRequest } from './client'

export interface Make {
  id: number
  name: string
  country: string
  brand_tier: string
}

export interface Model {
  id: number
  make_id: number
  name: string
  segment: string
  body_type: string
}

export interface Generation {
  id: number
  model_id: number
  name: string
  year_from: number
  year_to: number | null
  restyling: number
}

export interface Modification {
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

export interface Region {
  id: number
  name: string
  iso_code: string
  federal_district: string
  climate_zone: string
}

export const catalogApi = {
  listMakes: (query: string) =>
    apiRequest<Make[]>(`/api/catalog/makes?q=${encodeURIComponent(query)}`),
  listRegions: () => apiRequest<Region[]>('/api/catalog/regions'),
  listModelsByMake: (makeId: number) => apiRequest<Model[]>(`/api/catalog/makes/${makeId}/models`),
  listGenerationsByModel: (modelId: number) =>
    apiRequest<Generation[]>(`/api/catalog/models/${modelId}/generations`),
  listModificationsByGeneration: (generationId: number) =>
    apiRequest<Modification[]>(`/api/catalog/generations/${generationId}/modifications`),
  getModification: (modificationId: number) =>
    apiRequest<Modification>(`/api/catalog/modifications/${modificationId}`),
}

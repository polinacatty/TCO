import { describe, expect, it } from 'vitest'

import { toScenarioProfile } from './scenarioProfile'

describe('toScenarioProfile', () => {
  it('maps profile values with weights preset', () => {
    const result = toScenarioProfile({
      region_id: 77,
      annual_mileage_km: 21000,
      driver_age: 31,
      driver_experience_years: 8,
      osago_unlimited_drivers: true,
      use_dealer_service: false,
      include_kasko: true,
    })

    expect(result).toEqual({
      region_id: 77,
      annual_mileage_km: 21000,
      driver_age: 31,
      driver_experience_years: 8,
      osago_unlimited_drivers: true,
      use_dealer_service: false,
      include_kasko: true,
      weights_preset: 'balanced',
    })
  })

  it('returns defaults when profile is missing', () => {
    expect(toScenarioProfile(undefined)).toEqual({
      region_id: 1,
      annual_mileage_km: 15000,
      driver_age: 35,
      driver_experience_years: 10,
      osago_unlimited_drivers: false,
      use_dealer_service: false,
      include_kasko: false,
      weights_preset: 'balanced',
    })
  })
})

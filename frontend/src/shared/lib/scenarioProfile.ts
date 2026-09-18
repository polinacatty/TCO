import type { ProfilePayload } from '../api/profile'
import type { ScenarioProfilePayload } from '../api/scenarios'

export function toScenarioProfile(profile: ProfilePayload | undefined): ScenarioProfilePayload {
  const driverAge = Math.min(Math.max(profile?.driver_age ?? 35, 18), 99)
  const driverExperienceYears = Math.min(
    Math.max(profile?.driver_experience_years ?? 10, 0),
    Math.max(driverAge - 16, 0),
  )

  return {
    region_id: Math.min(Math.max(profile?.region_id ?? 1, 0), 100),
    annual_mileage_km: Math.min(Math.max(profile?.annual_mileage_km ?? 15000, 1000), 200000),
    driver_age: driverAge,
    driver_experience_years: driverExperienceYears,
    osago_unlimited_drivers: profile?.osago_unlimited_drivers ?? false,
    use_dealer_service: profile?.use_dealer_service ?? false,
    include_kasko: profile?.include_kasko ?? false,
    weights_preset: 'balanced',
  }
}

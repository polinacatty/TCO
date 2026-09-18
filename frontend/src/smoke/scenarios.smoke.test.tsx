import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { App } from '../app/App'
import { useAuthStore } from '../features/auth/model/useAuthStore'

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('Scenarios smoke flow', () => {
  it('opens scenarios list and navigates to details', async () => {
    useAuthStore.setState({
      accessToken: 'test-token',
      user: { id: 'u-1', email: 'user@test.local', hasProfile: true },
      isAuthenticated: true,
      isBootstrapping: false,
    })

    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)

      if (url.includes('/api/auth/me')) {
        return jsonResponse({
          id: 'u-1',
          email: 'user@test.local',
          has_profile: true,
        })
      }

      if (url.includes('/api/profile')) {
        return jsonResponse({
          region_id: 77,
          annual_mileage_km: 18000,
          driver_age: 34,
          driver_experience_years: 11,
          osago_unlimited_drivers: false,
          use_dealer_service: false,
          include_kasko: false,
        })
      }

      if (url.includes('/api/scenarios?')) {
        return jsonResponse({
          items: [
            {
              id: 'sc-1',
              name: 'Family Sedan',
              horizon_years: 5,
              modifications_count: 2,
              summary_total_tco_rub: 8900000,
              created_at: new Date().toISOString(),
            },
          ],
          next_cursor: null,
          has_more: false,
        })
      }

      if (url.endsWith('/api/scenarios/sc-1')) {
        return jsonResponse({
          id: 'sc-1',
          name: 'Family Sedan',
          horizon_years: 5,
          profile: {
            region_id: 77,
            annual_mileage_km: 18000,
            driver_age: 34,
            driver_experience_years: 11,
            osago_unlimited_drivers: false,
            use_dealer_service: false,
            include_kasko: false,
            weights_preset: 'balanced',
          },
          options: {
            include_kasko: false,
            discount_rate_pct: 0,
          },
          summary_total_tco_rub: 8900000,
          cars: [
            {
              modification_id: 101,
              total_tco_rub: 4400000,
              custom_purchase_price_rub: null,
              age_at_purchase_months: 0,
            },
          ],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
      }

      if (url.endsWith('/api/catalog/modifications/101')) {
        return jsonResponse({
          id: 101,
          make: 'Toyota',
          model: 'Camry',
          generation: 'XV70',
          trim_name: 'Elegance',
          year_from: 2021,
          year_to: null,
          body_type: 'sedan',
          segment: 'D',
          power_hp: 181,
          fuel_type: 'petrol',
          transmission: 'automatic',
          drive: 'fwd',
          fuel_consumption_combined_l_100km: 7.5,
          msrp_new_rub: 3600000,
        })
      }

      return jsonResponse({ detail: 'not mocked' }, 404)
    })

    window.history.pushState({}, '', '/scenarios')
    const user = userEvent.setup()
    render(<App />)

    await screen.findByRole('heading', { name: 'Сценарии' })
    await screen.findByText(/Family Sedan/i)

    await user.click(await screen.findByRole('button', { name: 'Открыть' }))

    await waitFor(() => {
      expect(window.location.pathname).toBe('/scenarios/sc-1')
    })
    await screen.findByRole('heading', { name: 'Family Sedan' })
  })
})

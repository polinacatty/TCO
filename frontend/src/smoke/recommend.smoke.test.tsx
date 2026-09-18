import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { App } from '../app/App'

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('Recommend smoke flow', () => {
  it('runs recommendation and navigates to compare', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)

      if (url.includes('/api/auth/refresh')) {
        return jsonResponse({ detail: 'unauthorized' }, 401)
      }

      if (url.includes('/api/tco/recommend')) {
        return jsonResponse({
          items: [
            {
              rank: 1,
              score: 0.91,
              is_pareto_optimal: true,
              modification: {
                id: 201,
                make: 'Skoda',
                model: 'Octavia',
                generation: 'A8',
                trim_name: 'Style',
                year_from: 2022,
                year_to: null,
                body_type: 'sedan',
                segment: 'C',
                power_hp: 150,
                fuel_type: 'petrol',
                transmission: 'automatic',
                drive: 'fwd',
                fuel_consumption_combined_l_100km: 6.4,
                msrp_new_rub: 2900000,
              },
              tco_total_rub: 4200000,
              explanation_ru: 'Сбалансирован по цене и эксплуатационным расходам.',
            },
            {
              rank: 2,
              score: 0.87,
              is_pareto_optimal: false,
              modification: {
                id: 202,
                make: 'Kia',
                model: 'K5',
                generation: 'DL3',
                trim_name: 'Luxe',
                year_from: 2021,
                year_to: null,
                body_type: 'sedan',
                segment: 'D',
                power_hp: 150,
                fuel_type: 'petrol',
                transmission: 'automatic',
                drive: 'fwd',
                fuel_consumption_combined_l_100km: 7.2,
                msrp_new_rub: 3100000,
              },
              tco_total_rub: 4450000,
              explanation_ru: 'Комфортный вариант с предсказуемой амортизацией.',
            },
          ],
          total_candidates: 2,
          weights: { tco_5y: 0.3, purchase_price: 0.2 },
          metrics: { ndcg_at_k: null, diversity_at_k: 2, coverage_ratio: 1, stability_at_k: 1 },
          computed_at: new Date().toISOString(),
        })
      }

      if (url.includes('/api/catalog/modifications/201')) {
        return jsonResponse({
          id: 201,
          make: 'Skoda',
          model: 'Octavia',
          generation: 'A8',
          trim_name: 'Style',
          year_from: 2022,
          year_to: null,
          body_type: 'sedan',
          segment: 'C',
          power_hp: 150,
          fuel_type: 'petrol',
          transmission: 'automatic',
          drive: 'fwd',
          fuel_consumption_combined_l_100km: 6.4,
          msrp_new_rub: 2900000,
        })
      }

      if (url.includes('/api/catalog/modifications/202')) {
        return jsonResponse({
          id: 202,
          make: 'Kia',
          model: 'K5',
          generation: 'DL3',
          trim_name: 'Luxe',
          year_from: 2021,
          year_to: null,
          body_type: 'sedan',
          segment: 'D',
          power_hp: 150,
          fuel_type: 'petrol',
          transmission: 'automatic',
          drive: 'fwd',
          fuel_consumption_combined_l_100km: 7.2,
          msrp_new_rub: 3100000,
        })
      }

      return jsonResponse({ detail: 'not mocked' }, 404)
    })

    window.history.pushState({}, '', '/recommend')
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('button', { name: 'Подобрать' }))
    await screen.findByText(/Skoda Octavia/i)

    const addButtons = await screen.findAllByRole('button', { name: 'Добавить в сравнение' })
    await user.click(addButtons[0])
    await user.click(addButtons[1])

    const toCompareButtons = await screen.findAllByRole('button', { name: 'К сравнению' })
    await user.click(toCompareButtons[0])

    await waitFor(() => {
      expect(window.location.pathname).toBe('/compare')
    })
  })
})

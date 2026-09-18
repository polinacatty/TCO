import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuthStore } from '../../features/auth/model/useAuthStore'
import { useCompareStore } from '../../features/compare/model/useCompareStore'
import { favoritesApi } from '../../shared/api/favorites'
import { Card } from '../../shared/ui/Card'
import type { TcoCalculateResponse } from '../../shared/api/tco'
import { Button } from '../../shared/ui/Button'

const YearlyChartPanel = lazy(async () =>
  import('./YearlyChartPanel').then((module) => ({
    default: module.YearlyChartPanel,
  })),
)

interface TcoSummaryPanelProps {
  data: TcoCalculateResponse | null
  selectedCar: { modificationId: number; label: string; makeModelLabel: string } | null
}

export function TcoSummaryPanel({ data, selectedCar }: TcoSummaryPanelProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const token = useAuthStore((state) => state.accessToken)
  const compareIds = useCompareStore((state) => state.modificationIds)
  const addCompareId = useCompareStore((state) => state.addId)
  const favoritesQuery = useQuery({
    queryKey: ['favorites', token],
    queryFn: () => favoritesApi.list(token),
    enabled: isAuthenticated && Boolean(token),
  })
  const favoriteIds = favoritesQuery.data?.items.map((item) => item.modification_id) ?? []
  const toggleFavoriteMutation = useMutation({
    mutationFn: (modificationId: number) =>
      favoriteIds.includes(modificationId)
        ? favoritesApi.remove(token, modificationId)
        : favoritesApi.add(token, modificationId),
    onSuccess: (response) => {
      queryClient.setQueryData(['favorites', token], response)
    },
  })
  const isFavorite = selectedCar ? favoriteIds.includes(selectedCar.modificationId) : false

  if (!data) {
    return (
      <Card>
        <p className="text-sm text-slate-500">
          Здесь появится результат расчета TCO.
        </p>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {selectedCar && (
        <Card className="relative">
          <Button
            type="button"
            variant="ghost"
            className={`absolute right-1 top-1 h-12 w-12 rounded-full p-0 ${
              isFavorite ? 'text-rose-600 hover:bg-rose-50' : 'text-slate-400 hover:bg-slate-100'
            }`}
            aria-label={isFavorite ? 'Убрать из избранного' : 'Добавить в избранное'}
            title={isFavorite ? 'Убрать из избранного' : 'Добавить в избранное'}
            disabled={toggleFavoriteMutation.isPending}
            onClick={() => {
              if (!isAuthenticated) {
                navigate('/login')
                return
              }
              toggleFavoriteMutation.mutate(selectedCar.modificationId)
            }}
          >
            <span aria-hidden="true" className="text-3xl leading-none">
              {isFavorite ? '♥' : '♡'}
            </span>
          </Button>
          <div className="pr-14">
            <p className="text-xs uppercase tracking-wide text-slate-500">Авто из расчета</p>
            <div className="mt-1 flex w-full items-center gap-3">
              <h3 className="text-2xl font-semibold text-slate-900">{selectedCar.makeModelLabel}</h3>
              <div className="ml-auto flex items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="rounded-lg px-3 py-1.5 text-xs"
                  disabled={compareIds.length >= 3 && !compareIds.includes(selectedCar.modificationId)}
                  onClick={() => addCompareId(selectedCar.modificationId)}
                >
                  {compareIds.includes(selectedCar.modificationId)
                    ? 'Уже в сравнении'
                    : compareIds.length >= 3
                      ? 'Добавить в сравнение невозможно (лимит 3 авто)'
                      : 'Добавить в сравнение'}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  className="rounded-lg px-3 py-1.5 text-xs"
                  disabled={compareIds.length < 2}
                  onClick={() => navigate('/compare')}
                >
                  К сравнению
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}
      <Card className="grid gap-4 sm:grid-cols-2">
        <Metric
          title="Цена нового автомобиля"
          value={`${data.purchase_price_rub.toLocaleString('ru-RU')} ₽`}
        />
        <Metric
          title="Прогноз перепродажи"
          value={`${data.predicted_resale_price_rub.toLocaleString('ru-RU')} ₽`}
        />
        <Metric title="Итоговый TCO" value={`${data.total_tco_rub.toLocaleString('ru-RU')} ₽`} />
        <Metric title="TCO на 1 км" value={`${data.total_tco_per_km_rub.toLocaleString('ru-RU')} ₽`} />
      </Card>
      <Card className="space-y-3">
        <h3 className="text-lg font-semibold">Компоненты TCO</h3>
        <div className="space-y-2">
          {Object.entries(data.components)
            .sort(([, left], [, right]) => right.total_rub - left.total_rub)
            .map(([code, component]) => (
              <div key={code} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-800">{toRuLabel(code)}</span>
                  <span className="text-slate-700">
                    {component.total_rub.toLocaleString('ru-RU')} ₽ ({component.share_pct.toFixed(2)}%)
                  </span>
                </div>
                <div className="h-2 rounded-full bg-slate-100">
                  <div
                    className="h-2 rounded-full bg-accent"
                    style={{ width: `${Math.min(component.share_pct, 100)}%` }}
                  />
                </div>
              </div>
            ))}
        </div>
      </Card>
      <Suspense
        fallback={
          <Card>
            <p className="text-sm text-slate-500">Загружаем графики...</p>
          </Card>
        }
      >
        <YearlyChartPanel data={data} />
      </Suspense>
    </div>
  )
}

function Metric({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 p-4">
      <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">{title}</p>
      <p className="text-xl font-semibold text-slate-900">{value}</p>
    </div>
  )
}

function toRuLabel(code: string): string {
  switch (code) {
    case 'depreciation':
      return 'Амортизация'
    case 'fuel':
      return 'Топливо'
    case 'osago':
      return 'ОСАГО'
    case 'kasko':
      return 'КАСКО'
    case 'transport_tax':
      return 'Транспортный налог'
    case 'maintenance':
      return 'ТО'
    case 'tyres':
      return 'Шины'
    default:
      return code
  }
}

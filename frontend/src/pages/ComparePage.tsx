import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { useAuthStore } from '../features/auth/model/useAuthStore'
import { CarAutocomplete } from '../features/car-autocomplete/ui/CarAutocomplete'
import { useCompareStore } from '../features/compare/model/useCompareStore'
import { catalogApi } from '../shared/api/catalog'
import { profileApi } from '../shared/api/profile'
import { scenariosApi } from '../shared/api/scenarios'
import { tcoApi, type CompareResponse, type TcoComponentCode } from '../shared/api/tco'
import type { ApiError } from '../shared/api/types'
import { Button } from '../shared/ui/Button'
import { Card } from '../shared/ui/Card'
import { StateBlock } from '../shared/ui/StateBlock'

export function ComparePage() {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const [autocompleteVersion, setAutocompleteVersion] = useState(0)
  const [wasAutoCompared, setWasAutoCompared] = useState(false)
  const token = useAuthStore((state) => state.accessToken)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const compareIds = useCompareStore((state) => state.modificationIds)
  const addCompareId = useCompareStore((state) => state.addId)
  const setCompareIds = useCompareStore((state) => state.setIds)
  const removeId = useCompareStore((state) => state.removeId)
  const clear = useCompareStore((state) => state.clear)
  const { data: profile } = useQuery({
    queryKey: ['compare-profile', token],
    queryFn: () => profileApi.get(token),
    enabled: isAuthenticated && Boolean(token),
  })

  const mutation = useMutation({
    mutationFn: tcoApi.compare,
  })
  const createScenarioMutation = useMutation({
    mutationFn: () =>
      scenariosApi.create(
        token,
        {
          modification_ids: normalizedCompareIds,
        },
        crypto.randomUUID(),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['saved-comparison-exists', token] })
      void queryClient.invalidateQueries({ queryKey: ['saved-comparisons', token] })
    },
  })

  const result = useMemo(() => {
    if (!mutation.data) return null
    return {
      ...mutation.data,
      items: [...mutation.data.items].sort((left, right) => left.total_tco_rub - right.total_tco_rub),
    }
  }, [mutation.data])
  const errorText =
    mutation.error &&
    ((mutation.error as ApiError).details?.errors?.[0]?.message ||
      (mutation.error as ApiError).details?.detail)
      ? ((mutation.error as ApiError).details?.errors?.[0]?.message ??
        (mutation.error as ApiError).details?.detail)
      : null

  const normalizedDriverAge = Math.min(Math.max(profile?.driver_age ?? 35, 18), 99)
  const normalizedDriverExperience = Math.min(
    Math.max(profile?.driver_experience_years ?? 10, 0),
    Math.max(normalizedDriverAge - 16, 0),
  )

  const canCompare = compareIds.length >= 2 && compareIds.length <= 3
  const normalizedCompareIds = useMemo(
    () => Array.from(new Set(compareIds)).sort((left, right) => left - right),
    [compareIds],
  )
  const savedComparisonExistsQuery = useQuery({
    queryKey: ['saved-comparison-exists', token, normalizedCompareIds.join(',')],
    queryFn: () => scenariosApi.exists(token, normalizedCompareIds),
    enabled: isAuthenticated && canCompare,
  })
  const isComparisonAlreadySaved = savedComparisonExistsQuery.data?.exists ?? false
  const prefilledCompareIds = (
    (location.state as { prefillCompareIds?: number[]; autoRunCompare?: boolean } | null)
      ?.prefillCompareIds ?? []
  )
  const shouldAutoRunCompare = Boolean(
    (location.state as { prefillCompareIds?: number[]; autoRunCompare?: boolean } | null)?.autoRunCompare,
  )
  const compareLabelsQueries = useQueries({
    queries: compareIds.map((id) => ({
      queryKey: ['compare-modification', id],
      queryFn: () => catalogApi.getModification(id),
    })),
  })
  const labelsById = useMemo(() => {
    const map = new Map<number, string>()
    for (const query of compareLabelsQueries) {
      if (!query.data) continue
      const car = query.data
      map.set(car.id, `${car.make} ${car.model} ${car.generation} ${car.trim_name ?? 'База'}`)
    }
    return map
  }, [compareLabelsQueries])

  useEffect(() => {
    if (prefilledCompareIds.length === 0) return
    setCompareIds(prefilledCompareIds)
    setWasAutoCompared(false)
    navigate('/compare', { replace: true })
  }, [navigate, prefilledCompareIds, setCompareIds])

  useEffect(() => {
    if (!shouldAutoRunCompare || wasAutoCompared) return
    if (!canCompare || mutation.isPending) return
    setWasAutoCompared(true)
    mutation.mutate({
      profile: {
        region_id: profile?.region_id ?? 1,
        annual_mileage_km: profile?.annual_mileage_km ?? 15000,
        driver_age: normalizedDriverAge,
        driver_experience_years: normalizedDriverExperience,
        osago_unlimited_drivers: profile?.osago_unlimited_drivers ?? false,
        use_dealer_service: profile?.use_dealer_service ?? false,
        include_kasko: profile?.include_kasko ?? false,
      },
      horizon_years: 5,
      include_kasko: profile?.include_kasko ?? false,
      modification_ids: compareIds,
    })
  }, [
    canCompare,
    compareIds,
    mutation,
    normalizedDriverAge,
    normalizedDriverExperience,
    profile,
    shouldAutoRunCompare,
    wasAutoCompared,
  ])

  const compareScrollClass =
    'space-y-4 lg:max-h-[calc(100vh-4.25rem-2rem-1rem)] lg:overflow-y-auto lg:overscroll-contain lg:pr-1'

  return (
    <div className={compareScrollClass}>
      <Card className="space-y-3">
        <h1 className="text-2xl font-semibold">Сравнение автомобилей</h1>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="mb-2 text-sm font-medium text-slate-800">Добавить авто в сравнение</p>
          {compareIds.length < 3 ? (
            <CarAutocomplete
              key={autocompleteVersion}
              onSelect={({ modificationId }) => {
                if (compareIds.includes(modificationId)) {
                  setAutocompleteVersion((prev) => prev + 1)
                  return
                }
                addCompareId(modificationId)
                setAutocompleteVersion((prev) => prev + 1)
              }}
            />
          ) : (
            <p className="text-sm text-slate-600">
              Лимит для сравнения достигнут: {compareIds.length} из 3 авто. Удалите один из выбранных,
              чтобы добавить новый.
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {compareIds.length === 0 && (
            <span className="text-sm text-slate-500">Пока ничего не добавлено в сравнение.</span>
          )}
          {compareIds.map((id) => (
            <span key={id} className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-sm">
              {labelsById.get(id) ?? `#${id}`}
              <button type="button" className="text-slate-500 hover:text-rose-600" onClick={() => removeId(id)}>
                x
              </button>
            </span>
          ))}
        </div>
        {errorText && <p className="text-sm text-rose-600">{errorText}</p>}
        {createScenarioMutation.error && (
          <p className="text-sm text-rose-600">
            {((createScenarioMutation.error as ApiError).details?.detail as string | undefined) ??
              'Не удалось сохранить сравнение'}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            disabled={!canCompare || mutation.isPending}
            onClick={() =>
              mutation.mutate({
                profile: {
                  region_id: profile?.region_id ?? 1,
                  annual_mileage_km: profile?.annual_mileage_km ?? 15000,
                  driver_age: normalizedDriverAge,
                  driver_experience_years: normalizedDriverExperience,
                  osago_unlimited_drivers: profile?.osago_unlimited_drivers ?? false,
                  use_dealer_service: profile?.use_dealer_service ?? false,
                  include_kasko: profile?.include_kasko ?? false,
                },
                horizon_years: 5,
                include_kasko: profile?.include_kasko ?? false,
                modification_ids: compareIds,
              })
            }
          >
            {mutation.isPending ? 'Сравниваем...' : 'Сравнить'}
          </Button>
          <Button type="button" variant="secondary" onClick={clear}>
            Очистить
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="ml-auto"
            disabled={
              !isAuthenticated ||
              !canCompare ||
              isComparisonAlreadySaved ||
              createScenarioMutation.isPending ||
              savedComparisonExistsQuery.isLoading
            }
            onClick={() => {
              createScenarioMutation.mutate()
            }}
          >
            {createScenarioMutation.isPending
              ? 'Сохраняем...'
              : isComparisonAlreadySaved
                ? 'Уже сохранено'
                : 'Сохранить сравнение'}
          </Button>
        </div>
      </Card>

      {!canCompare && (
        <StateBlock
          title="Недостаточно данных для сравнения"
          description="Добавь минимум 2 автомобиля для сравнения."
        />
      )}
      {mutation.isPending && (
        <StateBlock title="Сравнение выполняется" description="Рассчитываем дельты и собираем график..." />
      )}
      {result && result.items.length > 0 && (
        <>
          <KpiRow data={result} />
          <CompareChart data={result} />
          <CompareYearlyChart data={result} />
        </>
      )}
    </div>
  )
}

function KpiRow({ data }: { data: CompareResponse }) {
  const optimalTotal = data.items[0]?.total_tco_rub ?? 0
  const gridColumnsClass = data.items.length >= 3 ? 'md:grid-cols-3' : 'md:grid-cols-2'

  return (
    <div className={`grid gap-3 ${gridColumnsClass}`}>
      {data.items.map((item) => {
        const deltaVsOptimal = item.total_tco_rub - optimalTotal
        const isOptimal = item.total_tco_rub === optimalTotal
        return (
        <Card key={item.modification.id} className="flex flex-col gap-4 p-5">
          <div className="space-y-1">
            <p className="text-lg font-semibold leading-tight text-slate-900">
              {item.modification.make} {item.modification.model}
            </p>
            <p className="text-sm text-slate-600">
              {item.modification.generation} · {item.modification.trim_name ?? 'База'} ·{' '}
              {item.modification.power_hp} л.с.
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Итого TCO</p>
            <p className="text-2xl font-bold tabular-nums text-slate-900">
              {item.total_tco_rub.toLocaleString('ru-RU')} ₽
            </p>
          </div>
          {isOptimal ? (
            <p className="text-sm font-medium text-emerald-700">Оптимальное по стоимости TCO</p>
          ) : (
            <p className="text-sm font-medium text-rose-700">
              Дороже оптимального на {deltaVsOptimal.toLocaleString('ru-RU')} ₽
            </p>
          )}
        </Card>
      )})}
    </div>
  )
}

function CompareChart({ data }: { data: CompareResponse }) {
  const componentOrder: TcoComponentCode[] = [
    'depreciation',
    'fuel',
    'osago',
    'kasko',
    'transport_tax',
    'maintenance',
    'tyres',
  ]
  const series = data.items.map((item, index) => ({
    key: `car_${index + 1}`,
    label: `${item.modification.make} ${item.modification.model}`,
    color: ['#0f766e', '#2563eb', '#7c3aed'][index] ?? '#475569',
  }))
  const chartData = componentOrder.map((component) => {
    const row: Record<string, number | string> = { component: toRuLabel(component) }
    data.items.forEach((item, index) => {
      row[`car_${index + 1}`] = item.components_rub[component] ?? 0
    })
    return row
  })

  return (
    <Card className="h-[26rem]">
      <p className="mb-2 text-sm font-medium text-slate-800">Сравнение компонентов TCO</p>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} barGap={6} margin={{ top: 8, right: 16, left: 28, bottom: 12 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="component" />
          <YAxis
            width={80}
            tickFormatter={(value: number) =>
              `${new Intl.NumberFormat('ru-RU', { notation: 'compact' }).format(value)} ₽`
            }
          />
          <Tooltip
            formatter={(value: unknown) =>
              typeof value === 'number' ? `${value.toLocaleString('ru-RU')} ₽` : '0 ₽'
            }
          />
          <Legend />
          {series.map((item) => (
            <Bar key={item.key} dataKey={item.key} name={item.label} fill={item.color} radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </Card>
  )
}

function CompareYearlyChart({ data }: { data: CompareResponse }) {
  const maxYear = Math.max(...data.items.map((item) => item.yearly.length), 0)
  const series = data.items.map((item, index) => ({
    key: `car_${index + 1}`,
    label: `${item.modification.make} ${item.modification.model}`,
    color: ['#0f766e', '#2563eb', '#7c3aed'][index] ?? '#475569',
  }))

  const chartData = Array.from({ length: maxYear }, (_, yearIndex) => {
    const row: Record<string, number | string> = {
      year: `Год ${yearIndex + 1}`,
    }
    data.items.forEach((item, itemIndex) => {
      const point = item.yearly[yearIndex]
      row[`car_${itemIndex + 1}`] = point?.total_rub ?? 0
    })
    return row
  })

  return (
    <Card className="h-[26rem]">
      <p className="mb-2 text-sm font-medium text-slate-800">Декомпозиция TCO по годам</p>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 28, bottom: 12 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="year" />
          <YAxis
            width={80}
            tickFormatter={(value: number) =>
              `${new Intl.NumberFormat('ru-RU', { notation: 'compact' }).format(value)} ₽`
            }
          />
          <Tooltip
            formatter={(value: unknown) =>
              typeof value === 'number' ? `${value.toLocaleString('ru-RU')} ₽` : '0 ₽'
            }
          />
          <Legend />
          {series.map((item) => (
            <Line
              key={item.key}
              type="monotone"
              dataKey={item.key}
              name={item.label}
              stroke={item.color}
              strokeWidth={3}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Card>
  )
}

function toRuLabel(code: TcoComponentCode): string {
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
      return 'Налог'
    case 'maintenance':
      return 'ТО'
    case 'tyres':
      return 'Шины'
    default:
      return code
  }
}

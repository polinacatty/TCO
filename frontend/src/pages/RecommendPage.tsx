import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuthStore } from '../features/auth/model/useAuthStore'
import { useCompareStore } from '../features/compare/model/useCompareStore'
import { catalogApi } from '../shared/api/catalog'
import { favoritesApi } from '../shared/api/favorites'
import { profileApi } from '../shared/api/profile'
import { tcoApi, type RecommendResponse } from '../shared/api/tco'
import type { ApiError } from '../shared/api/types'
import {
  preventNegativeNumberInput,
  toNonNegativeNumber,
} from '../shared/lib/nonNegativeNumber'
import { Button } from '../shared/ui/Button'
import { Card } from '../shared/ui/Card'
import { Input } from '../shared/ui/Input'
import { StateBlock } from '../shared/ui/StateBlock'

const BODY_TYPE_OPTIONS = ['', 'sedan', 'hatchback', 'wagon', 'suv', 'crossover', 'coupe']
const FUEL_OPTIONS = ['', 'AI92', 'AI95', 'AI98', 'DIESEL', 'HYBRID', 'ELECTRIC']
const DRIVE_OPTIONS = ['', 'FWD', 'RWD', 'AWD', '4WD_PARTTIME']
const TRANSMISSION_OPTIONS = ['', 'MT', 'AT', 'DCT', 'CVT', 'DIRECT']
const SEGMENT_OPTIONS = ['', 'B', 'C', 'D', 'E', 'J_SUV', 'J_CROSS']
const PRICE_RANGE = { min: 500_000, max: 15_000_000, step: 100_000 }
const POWER_RANGE = { min: 70, max: 600, step: 5 }

export function RecommendPage() {
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
  const { data: profile } = useQuery({
    queryKey: ['recommend-profile', token],
    queryFn: () => profileApi.get(token),
    enabled: isAuthenticated && Boolean(token),
  })

  const [result, setResult] = useState<RecommendResponse | null>(null)
  const [apiErrorText, setApiErrorText] = useState<string | null>(null)
  const [filters, setFilters] = useState({
    purchase_price_min_rub: PRICE_RANGE.min,
    purchase_price_max_rub: PRICE_RANGE.max,
    body_type: '',
    fuel_type: '',
    drive: '',
    transmission: '',
    segment: '',
    power_min_hp: POWER_RANGE.min,
    power_max_hp: POWER_RANGE.max,
    top_n: 10,
  })
  const [profileOverrides, setProfileOverrides] = useState({
    region_id: profile?.region_id ?? 1,
    annual_mileage_km: profile?.annual_mileage_km ?? 15000,
    driver_age: profile?.driver_age ?? 35,
    driver_experience_years: profile?.driver_experience_years ?? 10,
    osago_unlimited_drivers: profile?.osago_unlimited_drivers ?? false,
    use_dealer_service: profile?.use_dealer_service ?? false,
    include_kasko: profile?.include_kasko ?? false,
  })

  const mutation = useMutation({
    mutationFn: tcoApi.recommend,
    onSuccess: (response) => setResult(response),
  })

  const resolvedRegionId = Math.min(Math.max(profile?.region_id ?? profileOverrides.region_id, 1), 100)
  const resolvedAnnualMileage = Math.min(
    Math.max(profile?.annual_mileage_km ?? profileOverrides.annual_mileage_km, 1000),
    200000,
  )
  const rawDriverAge = profile?.driver_age ?? profileOverrides.driver_age
  const rawDriverExperience = profile?.driver_experience_years ?? profileOverrides.driver_experience_years
  const normalizedDriverAge = Math.min(Math.max(rawDriverAge ?? 35, 18), 99)
  const normalizedDriverExperience = Math.min(
    Math.max(rawDriverExperience ?? 10, 0),
    Math.max(Math.min(normalizedDriverAge - 16, 80), 0),
  )

  const showDriverAgeInput =
    !isAuthenticated ||
    profile?.driver_age == null ||
    profile.driver_age < 18 ||
    profile.driver_age > 99 ||
    (profile?.driver_experience_years != null &&
      profile.driver_experience_years > Math.max(profile.driver_age - 16, 0))
  const showDriverExperienceInput =
    !isAuthenticated ||
    profile?.driver_experience_years == null ||
    profile?.driver_age == null ||
    (profile.driver_experience_years != null &&
      profile.driver_experience_years > Math.max(profile.driver_age - 16, 0))
  const ageForExperienceLimit = Math.min(
    Math.max(showDriverAgeInput ? profileOverrides.driver_age : (profile?.driver_age ?? 35), 18),
    99,
  )
  const maxExperienceByAge = Math.max(Math.min(ageForExperienceLimit - 16, 80), 0)
  const showRegionInput = !isAuthenticated || profile?.region_id == null
  const showMileageInput = !isAuthenticated || profile?.annual_mileage_km == null
  const showProfileParamsBlock =
    showRegionInput || showMileageInput || showDriverAgeInput || showDriverExperienceInput
  const { data: regions = [] } = useQuery({
    queryKey: ['regions-for-recommend'],
    queryFn: () => catalogApi.listRegions(),
    enabled: showRegionInput,
  })

  const columnScrollClass =
    'lg:max-h-[calc(100vh-4.25rem-2rem-1rem)] lg:overflow-y-auto lg:overscroll-contain'

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(340px,1fr),minmax(760px,1.6fr)] lg:items-start">
      <div className={columnScrollClass}>
      <Card className="space-y-4">
        <h1 className="text-2xl font-semibold">Подбор автомобилей</h1>

        <div className="grid gap-2 sm:grid-cols-2">
          <RangeFilter
            className="sm:col-span-2"
            label="Цена, ₽"
            min={PRICE_RANGE.min}
            max={PRICE_RANGE.max}
            step={PRICE_RANGE.step}
            minValue={filters.purchase_price_min_rub}
            maxValue={filters.purchase_price_max_rub}
            onChange={(nextMin, nextMax) =>
              setFilters((prev) => ({
                ...prev,
                purchase_price_min_rub: nextMin,
                purchase_price_max_rub: nextMax,
              }))
            }
            formatValue={(value) => `${value.toLocaleString('ru-RU')} ₽`}
          />
          <Select
            value={filters.body_type}
            options={BODY_TYPE_OPTIONS}
            onChange={(value) => setFilters((prev) => ({ ...prev, body_type: value }))}
            label="Тип кузова"
          />
          <Select
            value={filters.fuel_type}
            options={FUEL_OPTIONS}
            onChange={(value) => setFilters((prev) => ({ ...prev, fuel_type: value }))}
            label="Тип топлива"
          />
          <Select
            value={filters.drive}
            options={DRIVE_OPTIONS}
            onChange={(value) => setFilters((prev) => ({ ...prev, drive: value }))}
            label="Привод"
          />
          <Select
            value={filters.transmission}
            options={TRANSMISSION_OPTIONS}
            onChange={(value) => setFilters((prev) => ({ ...prev, transmission: value }))}
            label="КПП"
          />
          <Select
            value={filters.segment}
            options={SEGMENT_OPTIONS}
            onChange={(value) => setFilters((prev) => ({ ...prev, segment: value }))}
            label="Сегмент"
          />
          <RangeFilter
            className="sm:col-span-2"
            label="Мощность, л.с."
            min={POWER_RANGE.min}
            max={POWER_RANGE.max}
            step={POWER_RANGE.step}
            minValue={filters.power_min_hp}
            maxValue={filters.power_max_hp}
            onChange={(nextMin, nextMax) =>
              setFilters((prev) => ({
                ...prev,
                power_min_hp: nextMin,
                power_max_hp: nextMax,
              }))
            }
            formatValue={(value) => `${value.toLocaleString('ru-RU')} л.с.`}
          />
        </div>

        {showProfileParamsBlock && (
        <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-sm font-medium text-slate-800">Параметры профиля для подбора</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {showRegionInput && (
              <div className="space-y-1">
                <p className="text-sm text-slate-600">Регион проживания</p>
                <select
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-accent"
                  value={String(profileOverrides.region_id)}
                  onChange={(event) =>
                    setProfileOverrides((prev) => ({
                      ...prev,
                      region_id: Number(event.target.value),
                    }))
                  }
                >
                  {regions.map((region) => (
                    <option key={region.id} value={region.id}>
                      {region.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {showMileageInput && (
              <div className="space-y-1">
                <p className="text-sm text-slate-600">Пробег в год, км</p>
                <Input
                  placeholder="Например, 15000"
                  type="number"
                  min={1000}
                  max={200000}
                  value={String(profileOverrides.annual_mileage_km)}
                  onChange={(event) =>
                    setProfileOverrides((prev) => ({
                      ...prev,
                      annual_mileage_km: Math.min(
                        Math.max(1000, toNonNegativeNumber(event.target.value || '15000', 15000)),
                        200000,
                      ),
                    }))
                  }
                  onKeyDown={preventNegativeNumberInput}
                />
              </div>
            )}
            {showDriverAgeInput && (
              <div className="space-y-1">
                <p className="text-sm text-slate-600">Возраст водителя</p>
                <Input
                  placeholder="Например, 35"
                  type="number"
                  min={18}
                  max={99}
                  value={String(profileOverrides.driver_age)}
                  onChange={(event) =>
                    setProfileOverrides((prev) => {
                      const nextAge = Math.min(
                        Math.max(18, toNonNegativeNumber(event.target.value || '35', 35)),
                        99,
                      )
                      return {
                        ...prev,
                        driver_age: nextAge,
                        driver_experience_years: Math.min(
                          prev.driver_experience_years,
                          Math.max(Math.min(nextAge - 16, 80), 0),
                        ),
                      }
                    })
                  }
                  onKeyDown={preventNegativeNumberInput}
                />
              </div>
            )}
            {showDriverExperienceInput && (
              <div className="space-y-1">
                <p className="text-sm text-slate-600">Стаж вождения, лет</p>
                <Input
                  placeholder="Например, 10"
                  type="number"
                  min={0}
                  max={maxExperienceByAge}
                  value={String(Math.min(profileOverrides.driver_experience_years, maxExperienceByAge))}
                  onChange={(event) =>
                    setProfileOverrides((prev) => {
                      return {
                        ...prev,
                        driver_experience_years: Math.min(
                          Math.max(0, toNonNegativeNumber(event.target.value || '10', 10)),
                          maxExperienceByAge,
                        ),
                      }
                    })
                  }
                  onKeyDown={preventNegativeNumberInput}
                />
              </div>
            )}
          </div>
        </div>
        )}

        <div className="flex items-center gap-2">
          <p className="text-sm text-slate-600">Сколько автомобилей показать:</p>
          <div className="size-10 shrink-0">
            <Input
              placeholder="10"
              type="number"
              min={1}
              max={30}
              className="size-full rounded-md px-1 py-0 text-center [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              value={String(filters.top_n)}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  top_n: Math.min(Math.max(1, toNonNegativeNumber(event.target.value || '10', 10)), 30),
                }))
              }
              onKeyDown={preventNegativeNumberInput}
            />
          </div>
        </div>

        {apiErrorText && <p className="text-sm text-rose-600">{apiErrorText}</p>}
        <Button
          type="button"
          disabled={mutation.isPending}
          onClick={() => {
            setApiErrorText(null)
            mutation.mutate(
              {
                profile: {
                  region_id: resolvedRegionId,
                  annual_mileage_km: resolvedAnnualMileage,
                  driver_age: normalizedDriverAge,
                  driver_experience_years: normalizedDriverExperience,
                  osago_unlimited_drivers:
                    profile?.osago_unlimited_drivers ?? profileOverrides.osago_unlimited_drivers,
                  use_dealer_service: profile?.use_dealer_service ?? profileOverrides.use_dealer_service,
                  include_kasko: profile?.include_kasko ?? profileOverrides.include_kasko,
                },
                horizon_years: 5,
                top_n: Math.min(Math.max(filters.top_n, 1), 30),
                weights_preset: 'balanced',
                include_kasko: profile?.include_kasko ?? profileOverrides.include_kasko,
                filters: {
                  purchase_price_min_rub:
                    filters.purchase_price_min_rub > PRICE_RANGE.min
                      ? filters.purchase_price_min_rub
                      : undefined,
                  purchase_price_max_rub:
                    filters.purchase_price_max_rub < PRICE_RANGE.max
                      ? filters.purchase_price_max_rub
                      : undefined,
                  body_types: toArrayFilter(filters.body_type),
                  drives: toArrayFilter(filters.drive),
                  fuel_types: toArrayFilter(filters.fuel_type),
                  transmissions: toArrayFilter(filters.transmission),
                  segments: toArrayFilter(filters.segment),
                  power_min_hp: filters.power_min_hp > POWER_RANGE.min ? filters.power_min_hp : undefined,
                  power_max_hp: filters.power_max_hp < POWER_RANGE.max ? filters.power_max_hp : undefined,
                },
              },
              {
                onError: (error) => {
                  const typedError = error as ApiError
                  setApiErrorText(
                    typedError.details?.errors?.[0]?.message ||
                      typedError.details?.detail ||
                      'Не удалось выполнить подбор',
                  )
                },
              },
            )
          }}
        >
          {mutation.isPending ? 'Подбираем...' : 'Подобрать'}
        </Button>
      </Card>
      </div>

      <div className={`min-w-0 space-y-4 ${columnScrollClass}`}>
        {mutation.isPending && (
          <StateBlock
            title="Подбор выполняется"
            description="Считаем TCO и ранжируем подходящие варианты..."
          />
        )}
        {!mutation.isPending && !result && (
          <Card>
            <p className="text-sm text-slate-500">Здесь появится результат подбора автомобилей.</p>
          </Card>
        )}
        {!mutation.isPending && result && result.items.length === 0 && (
          <Card>
            <p className="text-sm text-slate-500">
              По выбранным фильтрам ничего не найдено. Расширьте диапазон или выберите «Любой» в части
              фильтров.
            </p>
          </Card>
        )}
        {result?.items.map((item) => {
          const isFavorite = favoriteIds.includes(item.modification.id)
          return (
          <Card key={item.modification.id} className="relative space-y-4 p-5">
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
                toggleFavoriteMutation.mutate(item.modification.id)
              }}
            >
              <span aria-hidden="true" className="text-3xl leading-none">
                {isFavorite ? '♥' : '♡'}
              </span>
            </Button>
            <div className="pr-14">
              <p className="text-xs uppercase text-slate-500">#{item.rank} | score {item.score.toFixed(4)}</p>
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h3 className="text-2xl font-semibold leading-tight">
                    {item.modification.make} {item.modification.model}
                  </h3>
                  <p className="mt-1 text-sm text-slate-600">
                    {item.modification.generation} · {item.modification.trim_name ?? 'База'} ·{' '}
                    {item.modification.power_hp} л.с.
                  </p>
                </div>
                <div className="ml-2 flex shrink-0 gap-5 text-right">
                  <div>
                    <p className="text-sm text-slate-500">Цена нового авто</p>
                    <p className="text-xl font-semibold tabular-nums text-slate-900">
                      {item.modification.msrp_new_rub.toLocaleString('ru-RU')} ₽
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">TCO 5 лет</p>
                    <p className="text-xl font-semibold tabular-nums text-slate-900">
                      {item.tco_total_rub.toLocaleString('ru-RU')} ₽
                    </p>
                  </div>
                </div>
              </div>
            </div>
            <div className="grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 sm:grid-cols-2 lg:grid-cols-3">
              <SpecItem label="Мощность" value={`${item.modification.power_hp} л.с.`} />
              <SpecItem label="Топливо" value={formatFuel(item.modification.fuel_type)} />
              <SpecItem label="КПП" value={formatTransmission(item.modification.transmission)} />
              <SpecItem label="Привод" value={formatDrive(item.modification.drive)} />
              <SpecItem label="Кузов / сегмент" value={`${item.modification.body_type} / ${item.modification.segment}`} />
              <SpecItem
                label="Расход (смеш.)"
                value={`${item.modification.fuel_consumption_combined_l_100km.toLocaleString('ru-RU')} л/100 км`}
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <Button
                type="button"
                variant="ghost"
                className="rounded-lg px-3 py-1.5 text-xs"
                onClick={() =>
                  navigate('/calculate', {
                    state: {
                      prefillCalculation: {
                        modificationId: item.modification.id,
                        label:
                          `${item.modification.make} ${item.modification.model} ${item.modification.generation} ${item.modification.trim_name ?? ''}`.trim(),
                        makeModelLabel: `${item.modification.make} ${item.modification.model}`.trim(),
                      },
                    },
                  })
                }
              >
                К подробному TCO
              </Button>
              <div className="ml-auto flex flex-wrap items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="rounded-lg px-3 py-1.5 text-xs"
                  disabled={compareIds.length >= 3 && !compareIds.includes(item.modification.id)}
                  onClick={() => addCompareId(item.modification.id)}
                >
                  {compareIds.includes(item.modification.id)
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
          </Card>
        )})}
      </div>
    </div>
  )
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: string[]
  onChange: (value: string) => void
}) {
  return (
    <label className="space-y-1 text-sm">
      <span className="text-slate-600">{label}</span>
      <select
        className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option || 'any'} value={option}>
            {option === '' ? 'Любой' : formatFilterOptionLabel(label, option)}
          </option>
        ))}
      </select>
    </label>
  )
}

function formatFilterOptionLabel(fieldLabel: string, value: string): string {
  if (fieldLabel === 'КПП') {
    const labels: Record<string, string> = {
      MT: 'Механика',
      AT: 'Автомат',
      DCT: 'Робот',
      CVT: 'Вариатор',
      DIRECT: 'Редуктор (электро)',
    }
    return labels[value] ?? value
  }
  if (fieldLabel === 'Привод') {
    const labels: Record<string, string> = {
      FWD: 'Передний',
      RWD: 'Задний',
      AWD: 'Полный',
      '4WD_PARTTIME': 'Подключаемый полный',
    }
    return labels[value] ?? value
  }
  if (fieldLabel === 'Тип топлива') {
    const labels: Record<string, string> = {
      AI92: 'Бензин АИ-92',
      AI95: 'Бензин АИ-95',
      AI98: 'Бензин АИ-98',
      DIESEL: 'Дизель',
      HYBRID: 'Гибрид',
      ELECTRIC: 'Электро',
    }
    return labels[value] ?? value
  }
  return value
}

function toArrayFilter(value: string): string[] {
  return value ? [value] : []
}

function SpecItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1 rounded-lg bg-white px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-sm font-medium text-slate-900">{value}</p>
    </div>
  )
}

function formatFuel(value: string): string {
  const labels: Record<string, string> = {
    petrol: 'Бензин',
    diesel: 'Дизель',
    hybrid: 'Гибрид',
    electric: 'Электро',
  }
  return labels[value] ?? value
}

function formatTransmission(value: string): string {
  const labels: Record<string, string> = {
    manual: 'Механика',
    automatic: 'Автомат',
    robot: 'Робот',
    cvt: 'Вариатор',
  }
  return labels[value] ?? value
}

function formatDrive(value: string): string {
  const labels: Record<string, string> = {
    fwd: 'Передний',
    rwd: 'Задний',
    awd: 'Полный',
  }
  return labels[value] ?? value
}

function RangeFilter({
  label,
  min,
  max,
  step,
  minValue,
  maxValue,
  onChange,
  formatValue,
  className = '',
}: {
  label: string
  min: number
  max: number
  step: number
  minValue: number
  maxValue: number
  onChange: (nextMin: number, nextMax: number) => void
  formatValue: (value: number) => string
  className?: string
}) {
  const minPercent = ((minValue - min) / (max - min)) * 100
  const maxPercent = ((maxValue - min) / (max - min)) * 100

  return (
    <div className={`space-y-2 ${className}`}>
      <p className="text-sm text-slate-600">{label}</p>
      <div className="relative h-6">
        <div className="absolute top-1/2 h-1 w-full -translate-y-1/2 rounded-full bg-slate-200" />
        <div
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-accent"
          style={{
            left: `${minPercent}%`,
            width: `${Math.max(maxPercent - minPercent, 0)}%`,
          }}
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={minValue}
          onChange={(event) => {
            const nextValue = Number(event.target.value)
            onChange(Math.min(nextValue, maxValue - step), maxValue)
          }}
          className="pointer-events-none absolute inset-0 h-6 w-full appearance-none bg-transparent
            [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent
            [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:h-4
            [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:appearance-none
            [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0
            [&::-moz-range-thumb]:bg-accent"
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={maxValue}
          onChange={(event) => {
            const nextValue = Number(event.target.value)
            onChange(minValue, Math.max(nextValue, minValue + step))
          }}
          className="pointer-events-none absolute inset-0 h-6 w-full appearance-none bg-transparent
            [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent
            [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:h-4
            [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:appearance-none
            [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-0
            [&::-moz-range-thumb]:bg-accent"
        />
      </div>
      <div className="flex items-center justify-between text-xs text-slate-600">
        <span>{formatValue(minValue)}</span>
        <span>{formatValue(maxValue)}</span>
      </div>
    </div>
  )
}

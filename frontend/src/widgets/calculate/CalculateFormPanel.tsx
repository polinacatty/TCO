import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { CarAutocomplete } from '../../features/car-autocomplete/ui/CarAutocomplete'
import { useAuthStore } from '../../features/auth/model/useAuthStore'
import { catalogApi } from '../../shared/api/catalog'
import { profileApi } from '../../shared/api/profile'
import type { ApiError } from '../../shared/api/types'
import { tcoApi, type TcoCalculateResponse } from '../../shared/api/tco'
import { preventNegativeNumberInput, toNonNegativeNumber } from '../../shared/lib/nonNegativeNumber'
import { Button } from '../../shared/ui/Button'
import { Card } from '../../shared/ui/Card'
import { Input } from '../../shared/ui/Input'

const HORIZON_OPTIONS = [3, 4, 5] as const

function formatHorizonLabel(years: (typeof HORIZON_OPTIONS)[number]): string {
  return years === 5 ? '5 лет' : `${years} года`
}

interface CalculateFormPanelProps {
  onCalculated: (result: TcoCalculateResponse) => void
  onSelectedCarChange?: (
    value: { modificationId: number; label: string; makeModelLabel: string } | null,
  ) => void
  initialSelection?: { modificationId: number; label: string; makeModelLabel: string } | null
  autoCalculateOnInit?: boolean
}

export function CalculateFormPanel({
  onCalculated,
  onSelectedCarChange,
  initialSelection,
  autoCalculateOnInit = false,
}: CalculateFormPanelProps) {
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null)
  const [modificationId, setModificationId] = useState<number | null>(null)
  const [horizonYears, setHorizonYears] = useState<(typeof HORIZON_OPTIONS)[number]>(5)
  const [apiErrorText, setApiErrorText] = useState<string | null>(null)
  const autoCalculatedForModification = useRef<number | null>(null)
  const [guestValues, setGuestValues] = useState({
    annual_mileage_km: 15000,
    region_id: 1,
    driver_age: 35,
    driver_experience_years: 10,
    osago_unlimited_drivers: false,
    use_dealer_service: false,
    include_kasko: false,
  })
  const [authOverrides, setAuthOverrides] = useState({
    annual_mileage_km: 15000,
    region_id: 1,
    driver_age: 35,
    driver_experience_years: 10,
    osago_unlimited_drivers: false,
    use_dealer_service: false,
    include_kasko: false,
  })
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const token = useAuthStore((state) => state.accessToken)
  const { data: profile, isLoading: isProfileLoading } = useQuery({
    queryKey: ['profile-for-calculate', token],
    queryFn: () => profileApi.get(token),
    enabled: isAuthenticated && Boolean(token),
  })
  const shouldLoadRegions = !isAuthenticated || (!isProfileLoading && profile?.region_id == null)
  const { data: regions = [], isLoading: isRegionsLoading, isError: isRegionsError } = useQuery({
    queryKey: ['regions'],
    queryFn: () => catalogApi.listRegions(),
    enabled: shouldLoadRegions,
  })
  const mutation = useMutation({
    mutationFn: tcoApi.calculate,
    onSuccess: onCalculated,
  })

  const effectiveValues = isAuthenticated
    ? {
        annual_mileage_km: authOverrides.annual_mileage_km,
        region_id: profile?.region_id ?? authOverrides.region_id,
        driver_age: profile?.driver_age ?? authOverrides.driver_age,
        driver_experience_years:
          profile?.driver_experience_years ?? authOverrides.driver_experience_years,
        osago_unlimited_drivers: authOverrides.osago_unlimited_drivers,
        use_dealer_service: profile?.use_dealer_service ?? authOverrides.use_dealer_service,
        include_kasko: authOverrides.include_kasko,
      }
    : guestValues
  const normalizedAnnualMileage = Math.min(Math.max(effectiveValues.annual_mileage_km, 1000), 200000)
  const normalizedRegionId = Math.min(Math.max(effectiveValues.region_id, 0), 100)
  const normalizedDriverAge = Math.min(Math.max(effectiveValues.driver_age, 18), 99)
  const normalizedDriverExperience = Math.min(
    Math.max(effectiveValues.driver_experience_years, 0),
    Math.max(normalizedDriverAge - 16, 0),
  )
  const ageForExperienceLimit = isAuthenticated
    ? Math.min(Math.max(profile?.driver_age ?? authOverrides.driver_age, 18), 99)
    : Math.min(Math.max(guestValues.driver_age, 18), 99)
  const maxExperienceByAge = Math.max(ageForExperienceLimit - 16, 0)

  useEffect(() => {
    if (!initialSelection) return
    setSelectedLabel(initialSelection.label)
    setModificationId(initialSelection.modificationId)
    onSelectedCarChange?.(initialSelection)
  }, [initialSelection, onSelectedCarChange])

  const submitCalculation = (targetModificationId: number) => {
    setApiErrorText(null)
    mutation.mutate(
      {
        modification_id: targetModificationId,
        horizon_years: horizonYears,
        profile: {
          annual_mileage_km: normalizedAnnualMileage,
          region_id: normalizedRegionId,
          driver_age: normalizedDriverAge,
          driver_experience_years: normalizedDriverExperience,
          osago_unlimited_drivers: effectiveValues.osago_unlimited_drivers,
          use_dealer_service: effectiveValues.use_dealer_service,
          include_kasko: effectiveValues.include_kasko,
        },
        options: {
          include_kasko: effectiveValues.include_kasko,
          discount_rate_pct: 0,
        },
      },
      {
        onError: (error) => {
          const typedError = error as ApiError
          setApiErrorText(
            typedError.details?.errors?.[0]?.message ||
              typedError.details?.detail ||
              'Не удалось выполнить расчет',
          )
        },
      },
    )
  }

  useEffect(() => {
    if (!autoCalculateOnInit || modificationId === null) return
    if (isAuthenticated && isProfileLoading) return
    if (autoCalculatedForModification.current === modificationId) return
    autoCalculatedForModification.current = modificationId
    submitCalculation(modificationId)
  }, [autoCalculateOnInit, isAuthenticated, isProfileLoading, modificationId])

  useEffect(() => {
    if (!isAuthenticated || !profile) return
    setAuthOverrides((prev) => ({
      ...prev,
      annual_mileage_km: profile.annual_mileage_km ?? prev.annual_mileage_km,
      osago_unlimited_drivers: profile.osago_unlimited_drivers ?? prev.osago_unlimited_drivers,
      include_kasko: profile.include_kasko ?? prev.include_kasko,
      region_id: profile.region_id ?? prev.region_id,
      driver_age: profile.driver_age ?? prev.driver_age,
      driver_experience_years: profile.driver_experience_years ?? prev.driver_experience_years,
      use_dealer_service: profile.use_dealer_service ?? prev.use_dealer_service,
    }))
  }, [isAuthenticated, profile])

  useEffect(() => {
    if (isAuthenticated) {
      if (profile?.driver_experience_years != null) return
      if (authOverrides.driver_experience_years <= maxExperienceByAge) return
      setAuthOverrides((prev) => ({
        ...prev,
        driver_experience_years: maxExperienceByAge,
      }))
      return
    }
    if (guestValues.driver_experience_years <= maxExperienceByAge) return
    setGuestValues((prev) => ({
      ...prev,
      driver_experience_years: maxExperienceByAge,
    }))
  }, [
    authOverrides.driver_experience_years,
    guestValues.driver_experience_years,
    isAuthenticated,
    maxExperienceByAge,
    profile?.driver_experience_years,
  ])

  return (
    <Card className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">Калькулятор TCO</h2>
        <p className="text-sm text-slate-600">
          Заполните параметры расчета. Если часть данных уже есть в профиле, они подставятся автоматически.
        </p>
      </div>

      <CarAutocomplete
        initialSelection={initialSelection}
        onSelect={(value) => {
          setSelectedLabel(value.label)
          setModificationId(value.modificationId)
          onSelectedCarChange?.(value)
        }}
      />
      {selectedLabel && (
        <p className="text-sm text-slate-700">
          Выбрано: <span className="font-medium">{selectedLabel}</span>
        </p>
      )}
      {!selectedLabel && (
        <p className="text-sm text-slate-500">Сначала выберите модификацию автомобиля.</p>
      )}
      {isAuthenticated && isProfileLoading && (
        <p className="text-sm text-slate-500">Загружаем профиль для авто-заполнения...</p>
      )}
      {shouldLoadRegions && isRegionsLoading && (
        <p className="text-sm text-slate-500">Загружаем регионы...</p>
      )}
      {shouldLoadRegions && isRegionsError && (
        <p className="text-sm text-rose-600">Не удалось загрузить список регионов.</p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1 sm:col-span-2 lg:col-span-1 lg:max-w-xs">
          <p className="text-xs font-medium text-slate-600">Годовой пробег, км</p>
          <Input
            value={String(
              isAuthenticated ? authOverrides.annual_mileage_km : guestValues.annual_mileage_km,
            )}
            type="number"
            min={0}
            step={1}
            placeholder="Пробег в год"
            onKeyDown={preventNegativeNumberInput}
            onChange={(event) => {
              const parsed = toNonNegativeNumber(event.target.value || '0')
              if (isAuthenticated) {
                setAuthOverrides((prev) => ({ ...prev, annual_mileage_km: parsed }))
              } else {
                setGuestValues((prev) => ({ ...prev, annual_mileage_km: parsed }))
              }
            }}
          />
        </div>
        {(!isAuthenticated || profile?.driver_age == null) && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-slate-600">Возраст водителя, лет</p>
            <Input
              value={String(isAuthenticated ? authOverrides.driver_age : guestValues.driver_age)}
              type="number"
              min={18}
              max={99}
              step={1}
              placeholder="Возраст водителя"
              onKeyDown={preventNegativeNumberInput}
              onChange={(event) => {
                const parsed = Math.min(Math.max(toNonNegativeNumber(event.target.value || '18'), 18), 99)
                if (isAuthenticated) {
                  setAuthOverrides((prev) => ({
                    ...prev,
                    driver_age: parsed,
                    driver_experience_years: Math.min(
                      prev.driver_experience_years,
                      Math.max(parsed - 16, 0),
                    ),
                  }))
                } else {
                  setGuestValues((prev) => ({
                    ...prev,
                    driver_age: parsed,
                    driver_experience_years: Math.min(
                      prev.driver_experience_years,
                      Math.max(parsed - 16, 0),
                    ),
                  }))
                }
              }}
            />
          </div>
        )}
        {(!isAuthenticated || profile?.driver_experience_years == null) && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-slate-600">Стаж вождения, лет</p>
            <Input
              value={String(
                Math.min(
                  isAuthenticated ? authOverrides.driver_experience_years : guestValues.driver_experience_years,
                  maxExperienceByAge,
                ),
              )}
              type="number"
              min={0}
              max={maxExperienceByAge}
              step={1}
              placeholder="Стаж вождения"
              onKeyDown={preventNegativeNumberInput}
              onChange={(event) => {
                const parsed = toNonNegativeNumber(event.target.value || '0')
                const normalizedParsed = Math.min(parsed, maxExperienceByAge)
                if (isAuthenticated) {
                  setAuthOverrides((prev) => ({ ...prev, driver_experience_years: normalizedParsed }))
                } else {
                  setGuestValues((prev) => ({ ...prev, driver_experience_years: normalizedParsed }))
                }
              }}
            />
          </div>
        )}
        {(!isAuthenticated || profile?.region_id == null) && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-slate-600">Регион расчета</p>
            <select
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
              value={String(isAuthenticated ? authOverrides.region_id : guestValues.region_id)}
              onChange={(event) => {
                const parsed = Number(event.target.value)
                if (isAuthenticated) {
                  setAuthOverrides((prev) => ({ ...prev, region_id: parsed }))
                } else {
                  setGuestValues((prev) => ({ ...prev, region_id: parsed }))
                }
              }}
            >
              {regions.map((region) => (
                <option key={region.id} value={region.id}>
                  {region.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <label className="sm:col-span-2 flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={isAuthenticated ? authOverrides.osago_unlimited_drivers : guestValues.osago_unlimited_drivers}
            onChange={(event) => {
              const checked = event.target.checked
              if (isAuthenticated) {
                setAuthOverrides((prev) => ({ ...prev, osago_unlimited_drivers: checked }))
              } else {
                setGuestValues((prev) => ({ ...prev, osago_unlimited_drivers: checked }))
              }
            }}
          />
          ОСАГО без ограничения водителей
        </label>
        {(!isAuthenticated || profile?.use_dealer_service == null) && (
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={isAuthenticated ? authOverrides.use_dealer_service : guestValues.use_dealer_service}
              onChange={(event) => {
                const checked = event.target.checked
                if (isAuthenticated) {
                  setAuthOverrides((prev) => ({ ...prev, use_dealer_service: checked }))
                } else {
                  setGuestValues((prev) => ({ ...prev, use_dealer_service: checked }))
                }
              }}
            />
            Обслуживание у дилера
          </label>
        )}
        <label className="sm:col-span-2 flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={isAuthenticated ? authOverrides.include_kasko : guestValues.include_kasko}
            onChange={(event) => {
              const checked = event.target.checked
              if (isAuthenticated) {
                setAuthOverrides((prev) => ({ ...prev, include_kasko: checked }))
              } else {
                setGuestValues((prev) => ({ ...prev, include_kasko: checked }))
              }
            }}
          />
          Включить КАСКО
        </label>
      </div>
      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-600">Срок расчета TCO</p>
        <div className="inline-grid grid-cols-3 rounded-xl border border-slate-300 bg-white p-1">
          {HORIZON_OPTIONS.map((years) => (
            <button
              key={years}
              type="button"
              className={[
                'rounded-lg px-3 py-2 text-sm font-medium transition',
                horizonYears === years
                  ? 'bg-accent text-accent-foreground shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100',
              ].join(' ')}
              onClick={() => setHorizonYears(years)}
            >
              {formatHorizonLabel(years)}
            </button>
          ))}
        </div>
      </div>
      {apiErrorText && <p className="text-sm text-rose-600">{apiErrorText}</p>}
      <Button
        type="button"
        disabled={mutation.isPending || modificationId === null}
        onClick={() => {
          submitCalculation(modificationId as number)
        }}
      >
        {mutation.isPending ? 'Рассчитываем...' : 'Рассчитать TCO'}
      </Button>
    </Card>
  )
}


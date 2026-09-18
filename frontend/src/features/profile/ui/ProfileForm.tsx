import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'

import { authApi } from '../../../shared/api/auth'
import { catalogApi } from '../../../shared/api/catalog'
import { profileApi, type ProfilePayload } from '../../../shared/api/profile'
import type { ApiError } from '../../../shared/api/types'
import { preventNegativeNumberInput, toNonNegativeInt } from '../../../shared/lib/nonNegativeNumber'
import { Button } from '../../../shared/ui/Button'
import { Card } from '../../../shared/ui/Card'
import { Input } from '../../../shared/ui/Input'
import { useAuthStore } from '../../auth/model/useAuthStore'

type FormValues = {
  driver_age?: number | string
  annual_mileage_km?: number | string
  region_id?: number | string
  driver_experience_years?: number | string
  osago_unlimited_drivers?: boolean
  include_kasko?: boolean
}

export function ProfileForm() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const token = useAuthStore((state) => state.accessToken)
  const user = useAuthStore((state) => state.user)
  const setUserHasProfile = useAuthStore((state) => state.setUserHasProfile)
  const clear = useAuthStore((state) => state.clear)
  const [apiErrorText, setApiErrorText] = useState<string | null>(null)
  const [successText, setSuccessText] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['profile', token],
    queryFn: () => profileApi.get(token),
    enabled: Boolean(token),
  })
  const { data: regions = [] } = useQuery({
    queryKey: ['regions-for-profile'],
    queryFn: () => catalogApi.listRegions(),
  })
  const mutation = useMutation({
    mutationFn: (payload: ProfilePayload) => profileApi.put(token, payload),
  })
  const {
    register,
    handleSubmit,
    reset,
    getValues,
    formState: { errors },
  } = useForm<FormValues>({
    defaultValues: {
      driver_age: undefined,
      annual_mileage_km: undefined,
      region_id: undefined,
      driver_experience_years: undefined,
      osago_unlimited_drivers: false,
      include_kasko: false,
    },
  })

  const normalizeProfileToFormValues = (profile: ProfilePayload | null | undefined): FormValues => ({
    driver_age: profile?.driver_age ?? undefined,
    annual_mileage_km: profile?.annual_mileage_km ?? undefined,
    region_id: profile?.region_id != null ? String(profile.region_id) : undefined,
    driver_experience_years: profile?.driver_experience_years ?? undefined,
    osago_unlimited_drivers: Boolean(profile?.osago_unlimited_drivers),
    include_kasko: Boolean(profile?.include_kasko),
  })

  useEffect(() => {
    if (data) {
      reset(normalizeProfileToFormValues(data))
      setIsEditing(false)
    }
  }, [data, reset])

  const apiError = error as ApiError | null
  const profileMissing = isError && apiError?.status === 404
  const profileUnavailable = isError && !profileMissing
  const selectedRegionName = regions.find((region) => region.id === data?.region_id)?.name
  const hasProfile = Boolean(data)

  const formatOptionalNumber = (value: number | null | undefined) =>
    value == null ? 'не указано' : value
  const formatOptionalKm = (value: number | null | undefined) =>
    value == null ? 'не указано' : `${value.toLocaleString('ru-RU')} км`
  const formatOptionalBoolean = (value: boolean | undefined) => (value ? 'Да' : 'Нет')
  const toOptionalInt = (value: number | string | undefined): number | undefined => {
    if (value === undefined || value === '') {
      return undefined
    }
    return toNonNegativeInt(value, 0)
  }

  return (
    <div className="space-y-3">
      <Card className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-2xl font-semibold">Профиль пользователя</h1>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              void authApi.logout().finally(() => {
                clear()
                navigate('/calculate')
              })
            }}
          >
            Выйти
          </Button>
        </div>
        {isLoading && <p className="text-sm text-slate-500">Загружаем профиль...</p>}
        {profileUnavailable && (
          <p className="text-sm text-rose-600">
            Не удалось загрузить профиль. Попробуйте обновить страницу или войти заново.
          </p>
        )}

      {!isLoading && !profileUnavailable && !isEditing && (
        <div className="space-y-4">
          <ul className="space-y-2 text-sm text-slate-700">
            <li>
              <span className="font-medium">Email:</span> {user?.email ?? '—'}
            </li>
            <li>
              <span className="font-medium">Возраст:</span>{' '}
              {formatOptionalNumber(data?.driver_age)}
            </li>
            <li>
              <span className="font-medium">Регион:</span>{' '}
              {selectedRegionName ?? (data?.region_id != null ? `Регион ID ${data.region_id}` : 'не указано')}
            </li>
            <li>
              <span className="font-medium">Стаж вождения:</span>{' '}
              {formatOptionalNumber(data?.driver_experience_years)}
            </li>
            <li>
              <span className="font-medium">Годовой пробег:</span>{' '}
              {formatOptionalKm(data?.annual_mileage_km)}
            </li>
            <li>
              <span className="font-medium">ОСАГО без ограничения:</span>{' '}
              {formatOptionalBoolean(data?.osago_unlimited_drivers)}
            </li>
            <li>
              <span className="font-medium">Включать КАСКО:</span>{' '}
              {formatOptionalBoolean(data?.include_kasko)}
            </li>
          </ul>
          {successText && <p className="text-sm text-emerald-700">{successText}</p>}
          {apiErrorText && <p className="text-sm text-rose-600">{apiErrorText}</p>}
          <div className="flex items-center gap-3">
            <Button
              type="button"
              onClick={() => {
                setApiErrorText(null)
                setSuccessText(null)
                setIsEditing(true)
              }}
            >
              {hasProfile ? 'Изменить' : 'Заполнить профиль'}
            </Button>
          </div>
        </div>
      )}

      {!isLoading && !profileUnavailable && isEditing && (
        <form
          className="grid gap-3 sm:grid-cols-2"
          onSubmit={handleSubmit(async (values) => {
            setApiErrorText(null)
            setSuccessText(null)
            const payload = {
              region_id: toOptionalInt(values.region_id),
              annual_mileage_km: toOptionalInt(values.annual_mileage_km),
              driver_age: toOptionalInt(values.driver_age),
              driver_experience_years: toOptionalInt(values.driver_experience_years),
              osago_unlimited_drivers: Boolean(values.osago_unlimited_drivers),
              use_dealer_service: false,
              include_kasko: Boolean(values.include_kasko),
            }
            try {
              const saved = await mutation.mutateAsync(payload)
              queryClient.setQueryData(['profile', token], saved)
              queryClient.setQueryData(['dashboard-profile', token], saved)
              reset(normalizeProfileToFormValues(saved))
              setUserHasProfile(true)
              setIsEditing(false)
              setSuccessText('Профиль сохранен')
            } catch (error) {
              const typedError = error as ApiError
              if (typedError.status === 401) {
                navigate('/login')
                return
              }
              const detail = typedError.details?.detail
              const firstValidationMessage = typedError.details?.errors?.[0]?.message
              setApiErrorText(
                detail === 'Request body invalid'
                  ? firstValidationMessage || 'Проверьте заполненные поля профиля и попробуйте снова.'
                  : detail || 'Не удалось сохранить профиль',
              )
            }
          })}
        >
          <div className="space-y-1">
            <p className="text-xs font-medium text-slate-600">Email</p>
            <Input value={user?.email ?? ''} disabled placeholder="Email" />
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-slate-600">Возраст водителя, лет</p>
            <Input
              placeholder="Возраст"
              type="number"
              min={18}
              step={1}
              onKeyDown={preventNegativeNumberInput}
              {...register('driver_age', {
                validate: (value) => {
                  if (value === undefined || value === '') return true
                  const age = toNonNegativeInt(value, 0)
                  if (age < 18) return 'Возраст должен быть не меньше 18 лет'
                  if (age > 99) return 'Возраст должен быть не больше 99 лет'
                  return true
                },
              })}
            />
            {errors.driver_age && <p className="text-xs text-rose-600">{errors.driver_age.message}</p>}
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-slate-600">Регион проживания</p>
            <select
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-accent"
              {...register('region_id')}
            >
              <option value="">Выберите регион</option>
              {regions.map((region) => (
                <option key={region.id} value={String(region.id)}>
                  {region.name}
                </option>
              ))}
            </select>
            {errors.region_id && <p className="text-xs text-rose-600">{errors.region_id.message}</p>}
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-slate-600">Стаж вождения, лет</p>
            <Input
              placeholder="Стаж"
              type="number"
              min={0}
              step={1}
              onKeyDown={preventNegativeNumberInput}
              {...register('driver_experience_years', {
                validate: (value) => {
                  if (value === undefined || value === '') return true
                  const experience = toNonNegativeInt(value, 0)
                  const rawAge = getValues('driver_age')
                  if (rawAge === undefined || rawAge === '') {
                    return true
                  }
                  const age = toNonNegativeInt(rawAge, 0)
                  if (experience > 80) return 'Стаж должен быть не больше 80 лет'
                  if (age >= 18 && experience > age - 16) {
                    return `Для возраста ${age} стаж не может быть больше ${age - 16} лет`
                  }
                  return true
                },
              })}
            />
            {errors.driver_experience_years && (
              <p className="text-xs text-rose-600">{errors.driver_experience_years.message}</p>
            )}
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-slate-600">Годовой пробег, км</p>
            <Input
              placeholder="Пробег в год"
              type="number"
              min={1000}
              step={1}
              onKeyDown={preventNegativeNumberInput}
              {...register('annual_mileage_km', {
                validate: (value) => {
                  if (value === undefined || value === '') return true
                  const mileage = toNonNegativeInt(value, 0)
                  if (mileage < 1000) return 'Годовой пробег должен быть не меньше 1000 км'
                  if (mileage > 200000) return 'Годовой пробег должен быть не больше 200000 км'
                  return true
                },
              })}
            />
            {errors.annual_mileage_km && (
              <p className="text-xs text-rose-600">{errors.annual_mileage_km.message}</p>
            )}
          </div>
          <label className="sm:col-span-2 flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" {...register('osago_unlimited_drivers')} />
            ОСАГО без ограничения водителей
          </label>
          <label className="sm:col-span-2 flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" {...register('include_kasko')} />
            Включать КАСКО по умолчанию
          </label>
          {successText && <p className="sm:col-span-2 text-sm text-emerald-700">{successText}</p>}
          {apiErrorText && <p className="sm:col-span-2 text-sm text-rose-600">{apiErrorText}</p>}
          <div className="sm:col-span-2">
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? 'Сохраняем...' : 'Сохранить'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setApiErrorText(null)
                  setSuccessText(null)
                  setIsEditing(false)
                }}
              >
                Отмена
              </Button>
            </div>
          </div>
        </form>
      )}
      </Card>
      {!isLoading && !profileUnavailable && (
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" onClick={() => navigate('/favorites')}>
            Перейти к избранным
          </Button>
          <Button type="button" variant="secondary" onClick={() => navigate('/saved-comparisons')}>
            Перейти к сохранненым сравнениям
          </Button>
        </div>
      )}
    </div>
  )
}

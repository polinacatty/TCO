import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { authApi } from '../../../shared/api/auth'
import type { ApiError } from '../../../shared/api/types'
import { Button } from '../../../shared/ui/Button'
import { Card } from '../../../shared/ui/Card'
import { Input } from '../../../shared/ui/Input'
import { useAuthStore } from '../model/useAuthStore'

const schema = z
  .object({
    email: z.string().email('Введите корректный email'),
    password: z.string().min(8, 'Минимум 8 символов'),
    confirmPassword: z.string(),
    pdnConsent: z.boolean().refine(Boolean, 'Нужно согласие на обработку ПДн'),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ['confirmPassword'],
    message: 'Пароли должны совпадать',
  })

type FormValues = z.infer<typeof schema>

export function RegisterForm() {
  const navigate = useNavigate()
  const [apiErrorText, setApiErrorText] = useState<string | null>(null)
  const setSession = useAuthStore((state) => state.setSession)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { pdnConsent: false },
  })

  const onSubmit = async (values: FormValues) => {
    setApiErrorText(null)
    try {
      const response = await authApi.register({
        email: values.email,
        password: values.password,
        pdn_consent: values.pdnConsent,
      })
      setSession({
        accessToken: response.access_token,
        user: {
          id: response.user.id,
          email: response.user.email,
          hasProfile: response.user.has_profile,
        },
      })
      navigate('/profile')
    } catch (error) {
      const typedError = error as ApiError
      setApiErrorText(typedError.details?.detail || 'Не удалось завершить регистрацию')
    }
  }

  return (
    <Card className="mx-auto max-w-md space-y-4">
      <h1 className="text-2xl font-semibold">Регистрация</h1>
      <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
        <div className="space-y-1">
          <Input placeholder="Email" {...register('email')} />
          {errors.email && <p className="text-xs text-rose-600">{errors.email.message}</p>}
        </div>
        <div className="space-y-1">
          <Input type="password" placeholder="Пароль" {...register('password')} />
          {errors.password && <p className="text-xs text-rose-600">{errors.password.message}</p>}
        </div>
        <div className="space-y-1">
          <Input type="password" placeholder="Подтвердите пароль" {...register('confirmPassword')} />
          {errors.confirmPassword && (
            <p className="text-xs text-rose-600">{errors.confirmPassword.message}</p>
          )}
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" {...register('pdnConsent')} />
          Согласен на обработку персональных данных
        </label>
        {errors.pdnConsent && <p className="text-xs text-rose-600">{errors.pdnConsent.message}</p>}
        {apiErrorText && <p className="text-xs text-rose-600">{apiErrorText}</p>}
        <Button disabled={isSubmitting} type="submit" className="w-full">
          {isSubmitting ? 'Создаем...' : 'Создать аккаунт'}
        </Button>
      </form>
    </Card>
  )
}

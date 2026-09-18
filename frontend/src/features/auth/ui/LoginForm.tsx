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

const schema = z.object({
  email: z.string().email('Введите корректный email'),
  password: z.string().min(8, 'Минимум 8 символов'),
})

type FormValues = z.infer<typeof schema>

export function LoginForm() {
  const navigate = useNavigate()
  const [apiErrorText, setApiErrorText] = useState<string | null>(null)
  const setSession = useAuthStore((state) => state.setSession)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (values: FormValues) => {
    setApiErrorText(null)
    try {
      const response = await authApi.login(values)
      setSession({
        accessToken: response.access_token,
        user: {
          id: response.user.id,
          email: response.user.email,
          hasProfile: response.user.has_profile,
        },
      })
      navigate(response.user.has_profile ? '/dashboard' : '/profile')
    } catch (error) {
      const typedError = error as ApiError
      setApiErrorText(typedError.details?.detail || 'Не удалось выполнить вход')
    }
  }

  return (
    <Card className="mx-auto max-w-md space-y-4">
      <h1 className="text-2xl font-semibold">Вход</h1>
      <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
        <div className="space-y-1">
          <Input placeholder="Email" {...register('email')} />
          {errors.email && <p className="text-xs text-rose-600">{errors.email.message}</p>}
        </div>
        <div className="space-y-1">
          <Input type="password" placeholder="Пароль" {...register('password')} />
          {errors.password && <p className="text-xs text-rose-600">{errors.password.message}</p>}
        </div>
        {apiErrorText && <p className="text-xs text-rose-600">{apiErrorText}</p>}
        <Button disabled={isSubmitting} type="submit" className="w-full">
          {isSubmitting ? 'Входим...' : 'Войти'}
        </Button>
      </form>
    </Card>
  )
}

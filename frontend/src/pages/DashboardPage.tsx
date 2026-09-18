import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { useAuthStore } from '../features/auth/model/useAuthStore'
import { profileApi } from '../shared/api/profile'
import { Card } from '../shared/ui/Card'
import { StateBlock } from '../shared/ui/StateBlock'

const NEXT_ACTIONS = [
  {
    to: '/recommend',
    title: 'Подбор автомобиля',
    description: 'Получите список подходящих автомобилей по параметрам и бюджету.',
  },
  {
    to: '/compare',
    title: 'Сравнение моделей',
    description: 'Сравните 2-3 автомобиля по структуре затрат TCO.',
  },
  {
    to: '/saved-comparisons',
    title: 'Сохраненные сравнения',
    description: 'Открывайте сохраненные сравнения и быстро возвращайтесь к анализу.',
  },
  {
    to: '/favorites',
    title: 'Избранное',
    description: 'Храните карточки интересных автомобилей и открывайте их сразу в калькуляторе.',
  },
]

export function DashboardPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const token = useAuthStore((state) => state.accessToken)
  const { isLoading, isError, error } = useQuery({
    queryKey: ['dashboard-profile', token],
    queryFn: () => profileApi.get(token),
    enabled: Boolean(token),
  })
  const profileNotFound = isError && (error as { status?: number } | null)?.status === 404

  return (
    <div className="space-y-6">
      <Card className="space-y-3">
        <h1 className="text-3xl font-semibold">Рассчитайте полную стоимость владения автомобилем</h1>
        <p className="text-slate-600">Калькулятор учитывает ключевые компоненты TCO на горизонте 5 лет.</p>
        <Link
          to="/calculate"
          className="inline-flex rounded-xl bg-accent px-4 py-2 text-sm font-medium text-accent-foreground"
        >
          Новый расчет
        </Link>
      </Card>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
        <Card className="flex h-full flex-col lg:col-span-2">
          <h2 className="mb-2 text-lg font-semibold">Профиль</h2>
          {!isAuthenticated && (
            <p className="text-sm text-slate-600">
              Войдите, чтобы сохранить параметры расчета в профиле и не вводить их каждый раз.
            </p>
          )}
          {isAuthenticated && isLoading && (
            <p className="text-sm text-slate-500">Загружаем профиль...</p>
          )}
          {isAuthenticated && isError && !profileNotFound && (
            <StateBlock
              title="Профиль временно недоступен"
              description="Не удалось загрузить данные профиля, попробуйте обновить страницу."
              tone="error"
            />
          )}
          {isAuthenticated && !isLoading && !isError && (
            <p className="text-sm text-slate-600">
              Заполните профиль, чтобы ускорить расчеты и получать более точные результаты.
            </p>
          )}
          <Link
            to={isAuthenticated ? '/profile' : '/login'}
            className="mt-auto inline-block pt-3 text-sm font-medium text-accent"
          >
            {isAuthenticated ? 'Перейти' : 'Войти'}
          </Link>
        </Card>
        {NEXT_ACTIONS.map((action, index) => (
          <Card
            key={action.to}
            className={
              index >= 2
                ? 'flex h-full flex-col space-y-2 lg:col-span-3'
                : 'flex h-full flex-col space-y-2 lg:col-span-2'
            }
          >
            <h2 className="text-lg font-semibold text-slate-900">{action.title}</h2>
            <p className="flex-1 text-sm text-slate-600">{action.description}</p>
            <Link to={action.to} className="inline-block text-sm font-medium text-accent">
              Перейти
            </Link>
          </Card>
        ))}
      </div>
    </div>
  )
}

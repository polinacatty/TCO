import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import type { KeyboardEvent } from 'react'
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuthStore } from '../features/auth/model/useAuthStore'
import { catalogApi } from '../shared/api/catalog'
import type { Modification } from '../shared/api/catalog'
import { favoritesApi } from '../shared/api/favorites'
import { Button } from '../shared/ui/Button'
import { Card } from '../shared/ui/Card'
import { StateBlock } from '../shared/ui/StateBlock'

export function FavoritesPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const token = useAuthStore((state) => state.accessToken)
  const favoritesQuery = useQuery({
    queryKey: ['favorites', token],
    queryFn: () => favoritesApi.list(token),
    enabled: Boolean(token),
  })
  const favoriteIds = favoritesQuery.data?.items.map((item) => item.modification_id) ?? []
  const removeMutation = useMutation({
    mutationFn: (modificationId: number) => favoritesApi.remove(token, modificationId),
    onSuccess: (response) => {
      queryClient.setQueryData(['favorites', token], response)
    },
  })

  const favoriteQueries = useQueries({
    queries: favoriteIds.map((id) => ({
      queryKey: ['favorite-modification', id],
      queryFn: () => catalogApi.getModification(id),
    })),
  })

  const items = useMemo(
    () =>
      favoriteQueries
        .map((query) => query.data)
        .filter((item): item is Modification => item !== undefined),
    [favoriteQueries],
  )

  const openInCalculator = (item: Modification) => {
    navigate('/calculate', {
      state: {
        prefillCalculation: {
          modificationId: item.id,
          label: `${item.make} ${item.model} ${item.generation} ${item.trim_name ?? ''}`.trim(),
          makeModelLabel: `${item.make} ${item.model}`.trim(),
        },
      },
    })
  }

  const onCardKeyDown = (event: KeyboardEvent<HTMLDivElement>, item: Modification) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    openInCalculator(item)
  }

  return (
    <div className="flex flex-col gap-4 lg:max-h-[calc(100vh-4.25rem-2rem-1rem)]">
      <h1 className="shrink-0 text-2xl font-semibold">Избранное</h1>
      <div className="min-h-0 space-y-4 lg:flex-1 lg:overflow-y-auto lg:overscroll-contain">
      {favoriteIds.length === 0 && (
        <StateBlock
          title="Пока пусто"
          description="Добавляйте автомобили в избранное из подбора или результата расчета."
        />
      )}
      {items.map((item) => (
        <Card key={item.id} className="space-y-2">
          <div
            className="cursor-pointer rounded-lg transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            role="button"
            tabIndex={0}
            onClick={() => openInCalculator(item)}
            onKeyDown={(event) => onCardKeyDown(event, item)}
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">
                  {item.make} {item.model}
                </h3>
                <p className="text-sm text-slate-600">
                  {item.generation} · {item.trim_name ?? 'База'} · {item.power_hp} л.с.
                </p>
              </div>
              <p className="text-lg font-semibold">{item.msrp_new_rub.toLocaleString('ru-RU')} ₽</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              className="ml-auto"
              onClick={(event) => {
                event.stopPropagation()
                removeMutation.mutate(item.id)
              }}
            >
              Удалить
            </Button>
          </div>
        </Card>
      ))}
      </div>
    </div>
  )
}

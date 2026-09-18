import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import type { KeyboardEvent } from 'react'
import { Fragment, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuthStore } from '../features/auth/model/useAuthStore'
import { catalogApi, type Modification } from '../shared/api/catalog'
import { scenariosApi } from '../shared/api/scenarios'
import type { ApiError } from '../shared/api/types'
import { Button } from '../shared/ui/Button'
import { Card } from '../shared/ui/Card'
import { StateBlock } from '../shared/ui/StateBlock'

export function SavedComparisonsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const token = useAuthStore((state) => state.accessToken)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)

  const listQuery = useQuery({
    queryKey: ['saved-comparisons', token],
    queryFn: () => scenariosApi.list(token, { limit: 50 }),
    enabled: isAuthenticated || Boolean(token),
  })

  const openMutation = useMutation({
    mutationFn: async (payload: { id: string; modificationIds: number[] }) => payload,
    onSuccess: ({ modificationIds }) => {
      navigate('/compare', {
        state: {
          prefillCompareIds: modificationIds,
          autoRunCompare: true,
        },
      })
    },
  })
  const deleteMutation = useMutation({
    mutationFn: (comparisonId: string) => scenariosApi.delete(token, comparisonId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['saved-comparisons', token] })
      void queryClient.invalidateQueries({ queryKey: ['saved-comparison-exists', token] })
    },
  })

  const openSavedComparison = (id: string, modificationIds: number[]) => {
    if (openMutation.isPending) return
    openMutation.mutate({ id, modificationIds })
  }

  const onCardKeyDown = (event: KeyboardEvent<HTMLDivElement>, scenarioId: string, modificationIds: number[]) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    openSavedComparison(scenarioId, modificationIds)
  }

  const errorText =
    (listQuery.error as ApiError | null)?.details?.detail ??
    (openMutation.error as ApiError | null)?.details?.detail ??
    (deleteMutation.error as ApiError | null)?.details?.detail ??
    null

  const items = listQuery.data?.items ?? []
  const allModificationIds = useMemo(
    () => Array.from(new Set(items.flatMap((item) => item.modification_ids))),
    [items],
  )
  const modificationQueries = useQueries({
    queries: allModificationIds.map((id) => ({
      queryKey: ['saved-comparison-modification', id],
      queryFn: () => catalogApi.getModification(id),
    })),
  })
  const modificationById = useMemo(() => {
    const map = new Map<number, Modification>()
    for (const query of modificationQueries) {
      if (!query.data) continue
      map.set(query.data.id, query.data)
    }
    return map
  }, [modificationQueries])

  const formatModificationSubtitle = (modification: Modification) =>
    `${modification.generation} · ${modification.trim_name ?? 'База'} · ${modification.power_hp} л.с.`

  const renderComparisonTitle = (modificationIds: number[]) =>
    modificationIds.map((id, index) => {
      const modification = modificationById.get(id)
      const makeModelLabel = modification
        ? `${modification.make} ${modification.model}`
        : `Модель ${id}`
      return (
        <Fragment key={id}>
          {index > 0 && <span className="mx-4 self-center text-base text-slate-500">VS</span>}
          <span className="inline-flex flex-col">
            <span>{makeModelLabel}</span>
            {modification && (
              <span className="text-xs font-normal text-slate-600">
                {formatModificationSubtitle(modification)}
              </span>
            )}
          </span>
        </Fragment>
      )
    })

  return (
    <div className="flex flex-col gap-4 lg:max-h-[calc(100vh-4.25rem-2rem-1rem)]">
      <h1 className="shrink-0 text-2xl font-semibold">Сохраненные сравнения</h1>
      <div className="min-h-0 space-y-4 lg:flex-1 lg:overflow-y-auto lg:overscroll-contain">
      {errorText && <p className="text-sm text-rose-600">{errorText}</p>}
      {listQuery.isPending && (
        <StateBlock title="Загружаем сохраненные сравнения" description="Получаем список карточек..." />
      )}
      {!listQuery.isPending && items.length === 0 && (
        <StateBlock
          title="Пока пусто"
          description="Сохраните сравнение на странице сравнения, и оно появится здесь."
        />
      )}
      {!listQuery.isPending &&
        items.map((item) => (
        <Card key={item.id} className="space-y-2">
          <div className="flex items-end justify-between gap-3">
            <div
              className="cursor-pointer rounded-lg transition hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              role="button"
              tabIndex={0}
              onClick={() => openSavedComparison(item.id, item.modification_ids)}
              onKeyDown={(event) => onCardKeyDown(event, item.id, item.modification_ids)}
            >
              <h3 className="flex flex-wrap items-start text-lg font-semibold text-slate-900">
                {renderComparisonTitle(item.modification_ids)}
              </h3>
            </div>
            <Button
              type="button"
              variant="ghost"
              disabled={deleteMutation.isPending}
              onClick={(event) => {
                event.stopPropagation()
                deleteMutation.mutate(item.id)
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

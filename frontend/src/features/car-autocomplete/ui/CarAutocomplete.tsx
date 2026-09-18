import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import { catalogApi, type Make } from '../../../shared/api/catalog'
import { Input } from '../../../shared/ui/Input'

interface CarAutocompleteProps {
  onSelect: (value: { modificationId: number; label: string; makeModelLabel: string }) => void
  initialSelection?: { modificationId: number; label: string; makeModelLabel: string } | null
}

export function CarAutocomplete({ onSelect, initialSelection = null }: CarAutocompleteProps) {
  const [makeQuery, setMakeQuery] = useState('')
  const [modelQuery, setModelQuery] = useState('')
  const [selectedMakeId, setSelectedMakeId] = useState<number | null>(null)
  const [selectedMakeName, setSelectedMakeName] = useState<string | null>(null)
  const [selectedModelId, setSelectedModelId] = useState<number | null>(null)
  const [selectedGenerationId, setSelectedGenerationId] = useState<number | null>(null)
  const [selectedModificationId, setSelectedModificationId] = useState<number | null>(null)
  const [prefillSelection, setPrefillSelection] = useState<{
    modificationId: number
    label: string
    makeModelLabel: string
  } | null>(initialSelection)
  const makeSearchQueries = useMemo(() => buildMakeSearchQueries(makeQuery), [makeQuery])

  useEffect(() => {
    setPrefillSelection(initialSelection)
  }, [initialSelection])

  const { data: prefillModification } = useQuery({
    queryKey: ['modification-by-id', prefillSelection?.modificationId],
    queryFn: () => catalogApi.getModification(prefillSelection?.modificationId as number),
    enabled: prefillSelection !== null,
  })

  const { data: makes = [], isLoading: isMakesLoading } = useQuery({
    queryKey: ['makes', makeSearchQueries],
    queryFn: async () => {
      const batches = await Promise.all(makeSearchQueries.map((query) => catalogApi.listMakes(query)))
      const merged = new Map<number, Make>()
      for (const batch of batches) {
        for (const make of batch) {
          merged.set(make.id, make)
        }
      }
      return Array.from(merged.values()).sort((left, right) => left.name.localeCompare(right.name))
    },
    enabled: makeQuery.trim().length >= 1 && selectedMakeId === null,
  })
  const { data: models = [], isLoading: isModelsLoading, isError: isModelsError } = useQuery({
    queryKey: ['models', selectedMakeId],
    queryFn: () => catalogApi.listModelsByMake(selectedMakeId as number),
    enabled: selectedMakeId !== null,
  })
  const {
    data: generations = [],
    isLoading: isGenerationsLoading,
    isError: isGenerationsError,
  } = useQuery({
    queryKey: ['generations', selectedModelId],
    queryFn: () => catalogApi.listGenerationsByModel(selectedModelId as number),
    enabled: selectedModelId !== null,
  })
  const {
    data: modifications = [],
    isLoading: isModificationsLoading,
    isError: isModificationsError,
  } = useQuery({
    queryKey: ['modifications', selectedGenerationId],
    queryFn: () => catalogApi.listModificationsByGeneration(selectedGenerationId as number),
    enabled: selectedGenerationId !== null,
  })

  const filteredModels = useMemo(() => {
    if (!modelQuery.trim()) {
      return models
    }
    const q = modelQuery.toLowerCase()
    return models.filter((model) => model.name.toLowerCase().includes(q))
  }, [modelQuery, models])

  const selectedMake = makes.find((make) => make.id === selectedMakeId)
  const selectedModel = models.find((model) => model.id === selectedModelId)
  const selectedGeneration = generations.find((generation) => generation.id === selectedGenerationId)
  const selectedModification = modifications.find((item) => item.id === selectedModificationId)
  const isPrefillVisible =
    prefillSelection !== null &&
    selectedMakeId === null &&
    selectedModelId === null &&
    selectedGenerationId === null &&
    selectedModificationId === null

  return (
    <div className="space-y-2">
      {isPrefillVisible && (
        <div className="space-y-2 text-xs text-slate-700">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-1">
              Марка: {prefillModification?.make ?? prefillSelection.makeModelLabel.split(' ')[0]}
            </span>
            <button type="button" className="text-accent" onClick={() => setPrefillSelection(null)}>
              Изменить
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-1">
              Модель:{' '}
              {prefillModification?.model ??
                prefillSelection.makeModelLabel.split(' ').slice(1).join(' ')}
            </span>
            <button type="button" className="text-accent" onClick={() => setPrefillSelection(null)}>
              Изменить
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-1">
              Поколение: {prefillModification?.generation ?? '—'}
            </span>
            <button type="button" className="text-accent" onClick={() => setPrefillSelection(null)}>
              Изменить
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2 py-1">
              Модификация:{' '}
              {prefillModification
                ? `${prefillModification.trim_name ?? 'База'} | ${prefillModification.power_hp} л.с. | ${prefillModification.fuel_type.toUpperCase()}`
                : prefillSelection.label}
            </span>
            <button type="button" className="text-accent" onClick={() => setPrefillSelection(null)}>
              Изменить
            </button>
          </div>
        </div>
      )}
      {selectedMakeId === null && !isPrefillVisible && (
        <Input
          value={makeQuery}
          onChange={(event) => {
            setPrefillSelection(null)
            setMakeQuery(event.target.value)
            setSelectedMakeName(null)
            setSelectedMakeId(null)
            setSelectedModelId(null)
            setSelectedGenerationId(null)
            setSelectedModificationId(null)
          }}
          placeholder="Выберите авто (введите марку)"
        />
      )}
      {makeQuery.trim().length >= 1 && selectedMakeId === null && !isPrefillVisible && (
        <div className="rounded-xl border border-slate-200 bg-white p-2 text-sm">
          {isMakesLoading && <p className="text-slate-500">Ищем марки...</p>}
          {!isMakesLoading && makes.length === 0 && (
            <p className="text-slate-500">Ничего не найдено</p>
          )}
          {!isMakesLoading && makes.length > 0 && (
            <ul className="space-y-1">
              {makes.slice(0, 8).map((make) => (
                <li key={make.id}>
                  <button
                    type="button"
                    className="w-full rounded-lg px-2 py-1.5 text-left hover:bg-slate-100"
                    onClick={() => {
                      setSelectedMakeId(make.id)
                      setSelectedMakeName(make.name)
                      setMakeQuery(make.name)
                      setModelQuery('')
                      setSelectedGenerationId(null)
                      setSelectedModificationId(null)
                    }}
                  >
                    {make.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(selectedMake || selectedMakeName) && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-700">
          <span className="rounded-full bg-slate-100 px-2 py-1">
            Марка: {selectedMakeName ?? selectedMake?.name}
          </span>
          <button
            type="button"
            className="text-accent"
            onClick={() => {
              setPrefillSelection(null)
              setMakeQuery('')
              setSelectedMakeName(null)
              setModelQuery('')
              setSelectedMakeId(null)
              setSelectedModelId(null)
              setSelectedGenerationId(null)
              setSelectedModificationId(null)
            }}
          >
            Изменить
          </button>
        </div>
      )}

      {selectedMakeId !== null && selectedModelId === null && (
        <div className="space-y-2">
          <Input
            value={modelQuery}
            onChange={(event) => {
              setModelQuery(event.target.value)
              setSelectedModelId(null)
              setSelectedGenerationId(null)
            }}
            placeholder="Введите модель"
          />
          <div className="rounded-xl border border-slate-200 bg-white p-2 text-sm">
            {isModelsLoading && <p className="text-slate-500">Загружаем модели...</p>}
            {isModelsError && <p className="text-rose-600">Не удалось загрузить модели.</p>}
            {filteredModels.length === 0 && (
              <p className="text-slate-500">Модели не найдены</p>
            )}
            {filteredModels.length > 0 && (
              <ul className="max-h-52 space-y-1 overflow-auto">
                {filteredModels.map((model) => (
                  <li key={model.id}>
                    <button
                      type="button"
                      className="w-full rounded-lg px-2 py-1.5 text-left hover:bg-slate-100"
                      onClick={() => {
                        setSelectedModelId(model.id)
                        setModelQuery(model.name)
                        setSelectedGenerationId(null)
                        setSelectedModificationId(null)
                      }}
                    >
                      {model.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {selectedModel && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-700">
          <span className="rounded-full bg-slate-100 px-2 py-1">Модель: {selectedModel.name}</span>
          <button
            type="button"
            className="text-accent"
            onClick={() => {
              setModelQuery('')
              setSelectedModelId(null)
              setSelectedGenerationId(null)
              setSelectedModificationId(null)
            }}
          >
            Изменить
          </button>
        </div>
      )}

      {selectedModelId !== null && selectedGenerationId === null && (
        <select
          className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
          value={selectedGenerationId ?? ''}
          onChange={(event) => {
            const nextGenerationId = event.target.value ? Number(event.target.value) : null
            setSelectedGenerationId(nextGenerationId)
            setSelectedModificationId(null)
          }}
        >
          <option value="">Выберите поколение</option>
          {isGenerationsLoading && <option value="">Загружаем поколения...</option>}
          {isGenerationsError && <option value="">Ошибка загрузки поколений</option>}
          {generations.map((generation) => (
            <option key={generation.id} value={generation.id}>
              {generation.name} ({generation.year_from} - {generation.year_to ?? 'н.в.'})
            </option>
          ))}
        </select>
      )}

      {selectedGeneration && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-700">
          <span className="rounded-full bg-slate-100 px-2 py-1">
            Поколение: {selectedGeneration.name}
          </span>
          <button
            type="button"
            className="text-accent"
            onClick={() => {
              setSelectedGenerationId(null)
              setSelectedModificationId(null)
            }}
          >
            Изменить
          </button>
        </div>
      )}

      {selectedGenerationId !== null && selectedModificationId === null && (
        <select
          className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
          value={selectedModificationId ?? ''}
          onChange={(event) => {
            const value = Number(event.target.value)
            if (!value) {
              setSelectedModificationId(null)
              return
            }
            const modification = modifications.find((item) => item.id === value)
            if (!modification) return
            setSelectedModificationId(modification.id)
            onSelect({
              modificationId: modification.id,
              label: `${modification.make} ${modification.model} ${modification.generation} ${modification.trim_name ?? ''}`.trim(),
              makeModelLabel: `${modification.make} ${modification.model}`.trim(),
            })
          }}
        >
          <option value="">Выберите модификацию</option>
          {isModificationsLoading && <option value="">Загружаем модификации...</option>}
          {isModificationsError && <option value="">Ошибка загрузки модификаций</option>}
          {modifications.map((modification) => (
            <option key={modification.id} value={modification.id}>
              {modification.trim_name ?? 'База'} | {modification.power_hp} л.с. | {modification.fuel_type}
            </option>
          ))}
        </select>
      )}

      {selectedModification && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-700">
          <span className="rounded-full bg-slate-100 px-2 py-1">
            Модификация: {selectedModification.trim_name ?? 'База'} | {selectedModification.power_hp} л.с. |{' '}
            {selectedModification.fuel_type}
          </span>
          <button
            type="button"
            className="text-accent"
            onClick={() => {
              setSelectedModificationId(null)
            }}
          >
            Изменить
          </button>
        </div>
      )}
    </div>
  )
}

const CYRILLIC_TO_LATIN: Record<string, string> = {
  а: 'a',
  б: 'b',
  в: 'v',
  г: 'g',
  д: 'd',
  е: 'e',
  ё: 'e',
  ж: 'zh',
  з: 'z',
  и: 'i',
  й: 'y',
  к: 'k',
  л: 'l',
  м: 'm',
  н: 'n',
  о: 'o',
  п: 'p',
  р: 'r',
  с: 's',
  т: 't',
  у: 'u',
  ф: 'f',
  х: 'h',
  ц: 'ts',
  ч: 'ch',
  ш: 'sh',
  щ: 'sch',
  ъ: '',
  ы: 'y',
  ь: '',
  э: 'e',
  ю: 'yu',
  я: 'ya',
}

const MAKE_ALIASES: Record<string, string> = {
  москвич: 'moskvich',
  мерседес: 'mercedes',
  мерседесбенц: 'mercedes-benz',
  бмв: 'bmw',
  джили: 'geely',
  хавал: 'haval',
}

function buildMakeSearchQueries(rawQuery: string): string[] {
  const trimmed = rawQuery.trim()
  if (!trimmed) {
    return []
  }

  const queries = new Set<string>([trimmed])
  const normalizedRu = trimmed.toLowerCase().replace(/[^а-яё]/g, '')

  if (/[а-яё]/i.test(trimmed)) {
    const transliterated = transliterateToLatin(trimmed)
    if (transliterated) {
      queries.add(transliterated)
    }
    const alias = MAKE_ALIASES[normalizedRu]
    if (alias) {
      queries.add(alias)
    }
  }

  return Array.from(queries)
}

function transliterateToLatin(value: string): string {
  return value
    .toLowerCase()
    .split('')
    .map((char) => CYRILLIC_TO_LATIN[char] ?? char)
    .join('')
    .replace(/\s+/g, ' ')
    .trim()
}

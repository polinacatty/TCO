import { useState } from 'react'
import { useLocation } from 'react-router-dom'

import type { TcoCalculateResponse } from '../shared/api/tco'
import { CalculateFormPanel } from '../widgets/calculate/CalculateFormPanel'
import { TcoSummaryPanel } from '../widgets/calculate/TcoSummaryPanel'

export function CalculatePage() {
  const location = useLocation()
  const initialSelection =
    (location.state as
      | {
          prefillCalculation?: { modificationId: number; label: string; makeModelLabel: string }
        }
      | undefined)?.prefillCalculation ?? null
  const [result, setResult] = useState<TcoCalculateResponse | null>(null)
  const [selectedCar, setSelectedCar] = useState<{
    modificationId: number
    label: string
    makeModelLabel: string
  } | null>(null)

  const columnScrollClass =
    'lg:max-h-[calc(100vh-4.25rem-2rem-1rem)] lg:overflow-y-auto lg:overscroll-contain'

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(340px,1fr),minmax(760px,1.6fr)] lg:items-start">
      <div className={columnScrollClass}>
        <CalculateFormPanel
          onCalculated={setResult}
          onSelectedCarChange={setSelectedCar}
          initialSelection={initialSelection}
          autoCalculateOnInit={Boolean(initialSelection)}
        />
      </div>
      <div className={`min-w-0 space-y-4 ${columnScrollClass}`}>
        <TcoSummaryPanel data={result} selectedCar={selectedCar} />
      </div>
    </div>
  )
}

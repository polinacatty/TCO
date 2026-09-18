import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { TcoCalculateResponse, TcoComponentCode, TcoYearlyPoint } from '../../shared/api/tco'
import { Button } from '../../shared/ui/Button'
import { Card } from '../../shared/ui/Card'

type ChartMode = 'stacked' | 'line'

const SERIES_ORDER: TcoComponentCode[] = [
  'depreciation',
  'fuel',
  'osago',
  'kasko',
  'transport_tax',
  'maintenance',
  'tyres',
]

const SERIES_LABELS: Record<TcoComponentCode, string> = {
  depreciation: 'Амортизация',
  fuel: 'Топливо',
  osago: 'ОСАГО',
  kasko: 'КАСКО',
  transport_tax: 'Транспортный налог',
  maintenance: 'ТО',
  tyres: 'Шины',
}

const SERIES_COLORS: Record<TcoComponentCode, string> = {
  depreciation: '#0f766e',
  fuel: '#0284c7',
  osago: '#7c3aed',
  kasko: '#be185d',
  transport_tax: '#b45309',
  maintenance: '#16a34a',
  tyres: '#475569',
}

interface YearlyChartPanelProps {
  data: TcoCalculateResponse
}

export function YearlyChartPanel({ data }: YearlyChartPanelProps) {
  const [mode, setMode] = useState<ChartMode>('line')
  const chartData = useMemo(() => data.yearly.map(toChartPoint), [data.yearly])

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold">Динамика затрат по годам</h3>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant={mode === 'stacked' ? 'primary' : 'secondary'}
            onClick={() => setMode('stacked')}
          >
            Структура по годам
          </Button>
          <Button
            type="button"
            variant={mode === 'line' ? 'primary' : 'secondary'}
            onClick={() => setMode('line')}
          >
            Итог и накопление
          </Button>
        </div>
      </div>
      <div className="h-96 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {mode === 'stacked' ? (
            <BarChart data={chartData} barCategoryGap={28}>
              <CartesianGrid strokeDasharray="4 4" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="yearLabel" tick={{ fill: '#334155', fontSize: 12 }} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={formatCompactRub} tick={{ fill: '#475569', fontSize: 12 }} tickLine={false} axisLine={false} width={80} />
              <Tooltip
                formatter={formatTooltipValue}
                contentStyle={{ borderRadius: '12px', borderColor: '#cbd5e1' }}
                labelStyle={{ fontWeight: 600 }}
              />
              <Legend wrapperStyle={{ paddingTop: 12 }} />
              {SERIES_ORDER.map((code) => (
                <Bar
                  key={code}
                  dataKey={code}
                  stackId="tco"
                  fill={SERIES_COLORS[code]}
                  name={SERIES_LABELS[code]}
                  radius={code === 'tyres' ? [6, 6, 0, 0] : 0}
                />
              ))}
            </BarChart>
          ) : (
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="4 4" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="yearLabel" tick={{ fill: '#334155', fontSize: 12 }} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={formatCompactRub} tick={{ fill: '#475569', fontSize: 12 }} tickLine={false} axisLine={false} width={80} />
              <Tooltip
                formatter={formatTooltipValue}
                contentStyle={{ borderRadius: '12px', borderColor: '#cbd5e1' }}
                labelStyle={{ fontWeight: 600 }}
              />
              <Legend wrapperStyle={{ paddingTop: 12 }} />
              <Line
                type="monotone"
                dataKey="total_rub"
                stroke="#0f766e"
                strokeWidth={3}
                name="Итог в год"
                dot={{ r: 4, strokeWidth: 0, fill: '#0f766e' }}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="cumulative_rub"
                stroke="#334155"
                strokeWidth={2}
                name="Накопительный итог"
                dot={{ r: 3, strokeWidth: 0, fill: '#334155' }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

function toChartPoint(item: TcoYearlyPoint) {
  const byComponent = item.by_component ?? {}
  return {
    yearLabel: `Год ${item.year_index}`,
    total_rub: item.total_rub,
    cumulative_rub: item.cumulative_rub ?? item.total_rub,
    depreciation: byComponent.depreciation ?? 0,
    fuel: byComponent.fuel ?? 0,
    osago: byComponent.osago ?? 0,
    kasko: byComponent.kasko ?? 0,
    transport_tax: byComponent.transport_tax ?? 0,
    maintenance: byComponent.maintenance ?? 0,
    tyres: byComponent.tyres ?? 0,
  }
}

function formatCompactRub(value: number): string {
  return `${new Intl.NumberFormat('ru-RU', { notation: 'compact' }).format(value)} ₽`
}

function formatTooltipValue(value: unknown): string {
  if (typeof value !== 'number') {
    return '0 ₽'
  }
  return `${value.toLocaleString('ru-RU')} ₽`
}

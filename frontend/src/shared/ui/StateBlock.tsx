import { Card } from './Card'

interface StateBlockProps {
  title: string
  description: string
  tone?: 'neutral' | 'error'
}

export function StateBlock({ title, description, tone = 'neutral' }: StateBlockProps) {
  return (
    <Card>
      <h3 className="mb-1 text-base font-semibold text-slate-900">{title}</h3>
      <p className={tone === 'error' ? 'text-sm text-rose-700' : 'text-sm text-slate-600'}>
        {description}
      </p>
    </Card>
  )
}

import { Link } from 'react-router-dom'

import { Card } from '../shared/ui/Card'

export function NotFoundPage() {
  return (
    <Card className="mx-auto max-w-lg space-y-3 text-center">
      <h1 className="text-2xl font-semibold">Страница не найдена</h1>
      <p className="text-sm text-slate-600">Похоже, адрес введен неверно или страница была перемещена.</p>
      <div className="flex justify-center gap-3">
        <Link className="rounded-xl border border-slate-300 px-4 py-2 text-sm" to="/">
          На главную
        </Link>
        <Link className="rounded-xl bg-accent px-4 py-2 text-sm text-accent-foreground" to="/calculate">
          Открыть калькулятор
        </Link>
      </div>
    </Card>
  )
}

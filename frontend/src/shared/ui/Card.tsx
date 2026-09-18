import type { PropsWithChildren } from 'react'

import { cn } from '../lib/cn'

interface CardProps extends PropsWithChildren {
  className?: string
}

export function Card({ className, children }: CardProps) {
  return <section className={cn('rounded-2xl border border-slate-200 bg-white p-5 shadow-sm', className)}>{children}</section>
}

import type { ButtonHTMLAttributes } from 'react'

import { cn } from '../lib/cn'

type ButtonVariant = 'primary' | 'secondary' | 'ghost'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
}

export function Button({
  className,
  variant = 'primary',
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium transition',
        variant === 'primary' && 'bg-accent text-accent-foreground hover:opacity-95',
        variant === 'secondary' && 'border border-slate-300 bg-white text-slate-800 hover:bg-slate-50',
        variant === 'ghost' && 'text-slate-600 hover:bg-slate-100',
        className,
      )}
      {...props}
    />
  )
}

import { useEffect, useRef, useState, type PropsWithChildren } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { authApi } from '../../shared/api/auth'
import { useAuthStore } from '../../features/auth/model/useAuthStore'

export function AppLayout({ children }: PropsWithChildren) {
  const navigate = useNavigate()
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const clear = useAuthStore((state) => state.clear)
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false)
  const profileMenuRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!isProfileMenuOpen) return
    const handleClickOutside = (event: globalThis.MouseEvent) => {
      if (!profileMenuRef.current) return
      if (event.target instanceof Node && !profileMenuRef.current.contains(event.target)) {
        setIsProfileMenuOpen(false)
      }
    }
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsProfileMenuOpen(false)
      }
    }
    window.addEventListener('mousedown', handleClickOutside)
    window.addEventListener('keydown', handleEscape)
    return () => {
      window.removeEventListener('mousedown', handleClickOutside)
      window.removeEventListener('keydown', handleEscape)
    }
  }, [isProfileMenuOpen])

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="fixed inset-x-0 top-0 z-50 border-b border-slate-200 bg-white shadow-sm">
        <div className="mx-auto flex h-[4.25rem] w-full max-w-7xl items-center justify-between px-4">
          <Link to="/dashboard" className="text-lg font-semibold text-accent">
            TCO Calculator
          </Link>
          <nav className="flex items-center gap-3 text-[13px] font-semibold">
            <Link to="/dashboard" className="text-[15px] font-semibold text-slate-800 hover:text-accent">
              Главная
            </Link>
            <Link to="/calculate" className="text-slate-700 hover:text-accent">
              Калькулятор TCO
            </Link>
            <Link to="/recommend" className="text-slate-700 hover:text-accent">
              Подбор автомобиля
            </Link>
            <Link to="/compare" className="text-slate-700 hover:text-accent">
              Сравнение моделей
            </Link>
            {isAuthenticated && (
              <div className="relative" ref={profileMenuRef}>
                <button
                  type="button"
                  className="text-slate-700 hover:text-accent"
                  onClick={(event) => {
                    if (event.button !== 0) return
                    setIsProfileMenuOpen(false)
                    navigate('/profile')
                  }}
                  onContextMenu={(event) => {
                    event.preventDefault()
                    setIsProfileMenuOpen((prev) => !prev)
                  }}
                >
                  Профиль
                </button>
                {isProfileMenuOpen && (
                  <div className="absolute right-0 z-[60] mt-2 w-56 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
                    <Link
                      to="/favorites"
                      className="block rounded-lg px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                      onClick={() => setIsProfileMenuOpen(false)}
                    >
                      Избранное
                    </Link>
                    <Link
                      to="/saved-comparisons"
                      className="block rounded-lg px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
                      onClick={() => setIsProfileMenuOpen(false)}
                    >
                      Сохраненные сравнения
                    </Link>
                    <button
                      type="button"
                      className="mt-1 block w-full rounded-lg px-3 py-2 text-left text-sm font-semibold text-rose-700 hover:bg-rose-50"
                      onClick={() => {
                        setIsProfileMenuOpen(false)
                        void authApi.logout().finally(() => {
                          clear()
                        })
                      }}
                    >
                      Выйти
                    </button>
                  </div>
                )}
              </div>
            )}
            {!isAuthenticated && (
              <>
                <Link to="/login" className="text-slate-700 hover:text-accent">
                  Войти
                </Link>
                <Link
                  to="/register"
                  className="rounded-lg bg-accent px-2.5 py-1 text-[13px] font-semibold text-accent-foreground"
                >
                  Регистрация
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl px-4 pb-8 pt-[calc(4.25rem+2rem)]">{children}</main>
    </div>
  )
}

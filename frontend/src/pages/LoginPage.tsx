import { Link } from 'react-router-dom'

import { LoginForm } from '../features/auth/ui/LoginForm'

export function LoginPage() {
  return (
    <div className="space-y-4">
      <LoginForm />
      <p className="text-center text-sm text-slate-600">
        Нет аккаунта?{' '}
        <Link className="font-medium text-accent" to="/register">
          Зарегистрироваться
        </Link>
      </p>
    </div>
  )
}

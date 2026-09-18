import { Link } from 'react-router-dom'

import { RegisterForm } from '../features/auth/ui/RegisterForm'

export function RegisterPage() {
  return (
    <div className="space-y-4">
      <RegisterForm />
      <p className="text-center text-sm text-slate-600">
        Уже есть аккаунт?{' '}
        <Link className="font-medium text-accent" to="/login">
          Войти
        </Link>
      </p>
    </div>
  )
}

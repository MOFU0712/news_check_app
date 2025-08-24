import React, { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useForm } from 'react-hook-form'
import { LoginData } from '../types'
import { Eye, EyeOff, LogIn } from 'lucide-react'

const Login: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  
  const from = (location.state as any)?.from?.pathname || '/'

  const {
    register,
    handleSubmit,
    formState: { errors }
  } = useForm<LoginData>()

  const onSubmit = async (data: LoginData) => {
    setIsLoading(true)
    try {
      await login(data)
      navigate(from, { replace: true })
    } catch (error) {
      // Error handling is done in the API interceptor and AuthContext
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">
            ITニュース管理システム
          </h2>
          <p className="mt-2 text-gray-600">
            アカウントにサインインしてください
          </p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">
              メールアドレス
            </label>
            <input
              {...register('email', {
                required: 'メールアドレスは必須です',
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: '有効なメールアドレスを入力してください'
                }
              })}
              type="email"
              className="input-field mt-1"
              placeholder="user@example.com"
            />
            {errors.email && (
              <p className="mt-1 text-sm text-red-600">{errors.email.message}</p>
            )}
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">
              パスワード
            </label>
            <div className="mt-1 relative">
              <input
                {...register('password', {
                  required: 'パスワードは必須です',
                  minLength: {
                    value: 6,
                    message: 'パスワードは6文字以上で入力してください'
                  }
                })}
                type={showPassword ? 'text' : 'password'}
                className="input-field pr-10"
                placeholder="パスワードを入力"
              />
              <button
                type="button"
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? (
                  <EyeOff className="h-5 w-5 text-gray-400" />
                ) : (
                  <Eye className="h-5 w-5 text-gray-400" />
                )}
              </button>
            </div>
            {errors.password && (
              <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex justify-center items-center btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2" />
            ) : (
              <LogIn className="w-5 h-5 mr-2" />
            )}
            {isLoading ? '認証中...' : 'ログイン'}
          </button>

          <div className="text-center">
            <p className="text-sm text-gray-600">
              招待URLをお持ちの方は{' '}
              <Link to="/register" className="text-primary-600 hover:text-primary-500">
                こちらからアカウント作成
              </Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  )
}

export default Login
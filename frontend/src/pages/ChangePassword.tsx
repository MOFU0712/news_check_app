import React, { useState } from 'react'
import { useMutation } from 'react-query'
import { useNavigate } from 'react-router-dom'
import { Lock, Eye, EyeOff, AlertCircle, CheckCircle } from 'lucide-react'
import api from '../services/api'
import toast from 'react-hot-toast'
import { useAuth } from '../contexts/AuthContext'

interface PasswordChangeData {
  current_password: string
  new_password: string
}

const ChangePassword: React.FC = () => {
  const navigate = useNavigate()
  const { user, logout, refreshUser } = useAuth()
  const [formData, setFormData] = useState<PasswordChangeData>({
    current_password: '',
    new_password: ''
  })
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrentPassword, setShowCurrentPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const changePasswordMutation = useMutation(
    async (data: PasswordChangeData) => {
      const response = await api.post('/auth/change-password', data)
      return response.data
    },
    {
      onSuccess: async () => {
        toast.success('パスワードが正常に変更されました')
        // ユーザー情報を更新してからダッシュボードに遷移
        await refreshUser()
        navigate('/dashboard')
      },
      onError: (error: any) => {
        toast.error(`パスワード変更に失敗しました: ${error.response?.data?.detail || error.message}`)
      }
    }
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    // バリデーション
    if (!formData.current_password || !formData.new_password || !confirmPassword) {
      toast.error('すべてのフィールドを入力してください')
      return
    }

    if (formData.new_password !== confirmPassword) {
      toast.error('新しいパスワードと確認用パスワードが一致しません')
      return
    }

    if (formData.new_password.length < 6) {
      toast.error('新しいパスワードは6文字以上で入力してください')
      return
    }

    if (formData.current_password === formData.new_password) {
      toast.error('新しいパスワードは現在のパスワードと異なるものにしてください')
      return
    }

    changePasswordMutation.mutate(formData)
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <div className="mx-auto h-12 w-12 bg-primary-100 rounded-full flex items-center justify-center">
            <Lock className="h-6 w-6 text-primary-600" />
          </div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            パスワード変更
          </h2>
          <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <div className="flex items-start">
              <AlertCircle className="h-5 w-5 text-yellow-400 mt-0.5 mr-3 flex-shrink-0" />
              <div>
                <h3 className="text-sm font-medium text-yellow-800">初期パスワード変更が必要です</h3>
                <p className="mt-1 text-sm text-yellow-700">
                  セキュリティのため、管理者によって設定された初期パスワードを変更してください。
                </p>
              </div>
            </div>
          </div>
          <p className="mt-4 text-center text-sm text-gray-600">
            ログイン中のユーザー: <span className="font-medium">{user?.email}</span>
          </p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            {/* 現在のパスワード */}
            <div>
              <label htmlFor="current_password" className="block text-sm font-medium text-gray-700 mb-2">
                現在のパスワード
              </label>
              <div className="relative">
                <input
                  id="current_password"
                  name="current_password"
                  type={showCurrentPassword ? "text" : "password"}
                  required
                  className="input-field pr-10"
                  placeholder="現在のパスワードを入力"
                  value={formData.current_password}
                  onChange={(e) => setFormData({...formData, current_password: e.target.value})}
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                >
                  {showCurrentPassword ? (
                    <EyeOff className="h-4 w-4 text-gray-400" />
                  ) : (
                    <Eye className="h-4 w-4 text-gray-400" />
                  )}
                </button>
              </div>
            </div>

            {/* 新しいパスワード */}
            <div>
              <label htmlFor="new_password" className="block text-sm font-medium text-gray-700 mb-2">
                新しいパスワード
              </label>
              <div className="relative">
                <input
                  id="new_password"
                  name="new_password"
                  type={showNewPassword ? "text" : "password"}
                  required
                  className="input-field pr-10"
                  placeholder="新しいパスワードを入力（6文字以上）"
                  minLength={6}
                  value={formData.new_password}
                  onChange={(e) => setFormData({...formData, new_password: e.target.value})}
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                >
                  {showNewPassword ? (
                    <EyeOff className="h-4 w-4 text-gray-400" />
                  ) : (
                    <Eye className="h-4 w-4 text-gray-400" />
                  )}
                </button>
              </div>
            </div>

            {/* パスワード確認 */}
            <div>
              <label htmlFor="confirm_password" className="block text-sm font-medium text-gray-700 mb-2">
                新しいパスワード（確認）
              </label>
              <div className="relative">
                <input
                  id="confirm_password"
                  name="confirm_password"
                  type={showConfirmPassword ? "text" : "password"}
                  required
                  className="input-field pr-10"
                  placeholder="新しいパスワードを再入力"
                  minLength={6}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                >
                  {showConfirmPassword ? (
                    <EyeOff className="h-4 w-4 text-gray-400" />
                  ) : (
                    <Eye className="h-4 w-4 text-gray-400" />
                  )}
                </button>
              </div>
            </div>

            {/* パスワード一致チェック */}
            {confirmPassword && (
              <div className={`text-sm flex items-center ${
                formData.new_password === confirmPassword ? 'text-green-600' : 'text-red-600'
              }`}>
                <CheckCircle className="h-4 w-4 mr-1" />
                {formData.new_password === confirmPassword 
                  ? 'パスワードが一致しています' 
                  : 'パスワードが一致しません'
                }
              </div>
            )}
          </div>

          <div className="flex space-x-4">
            <button
              type="submit"
              className="btn-primary flex-1 flex justify-center items-center"
              disabled={changePasswordMutation.isLoading}
            >
              {changePasswordMutation.isLoading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  変更中...
                </>
              ) : (
                'パスワードを変更'
              )}
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="btn-secondary"
            >
              ログアウト
            </button>
          </div>
        </form>

        <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded-lg">
          <h4 className="text-sm font-medium text-gray-900 mb-2">パスワードの要件</h4>
          <ul className="text-xs text-gray-600 space-y-1">
            <li>• 6文字以上の文字数</li>
            <li>• 現在のパスワードとは異なること</li>
            <li>• 推奨：大文字、小文字、数字、記号を組み合わせる</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

export default ChangePassword
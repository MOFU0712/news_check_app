import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { Users, Plus, Edit, Trash2, Shield, User, Mail, Calendar, RefreshCw } from 'lucide-react'
import api from '../services/api'
import toast from 'react-hot-toast'
import { useAuth } from '../contexts/AuthContext'

interface User {
  id: string
  email: string
  is_active: boolean
  is_admin: boolean
  created_at: string
  updated_at: string
}

interface UserCreate {
  email: string
  password: string
  is_admin: boolean
}

interface UserUpdate {
  email?: string
  is_active?: boolean
  is_admin?: boolean
}

const UserManagement: React.FC = () => {
  const { user: currentUser, isAdmin } = useAuth()
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [formData, setFormData] = useState<UserCreate>({
    email: '',
    password: '',
    is_admin: false
  })

  // 管理者でない場合はアクセス拒否
  if (!isAdmin) {
    return (
      <div className="text-center py-12">
        <Shield className="w-16 h-16 text-red-500 mx-auto mb-4" />
        <h2 className="text-2xl font-bold text-gray-900 mb-4">アクセス拒否</h2>
        <p className="text-gray-600">この機能にアクセスするには管理者権限が必要です。</p>
      </div>
    )
  }

  // ユーザー一覧取得
  const { data: users, isLoading, error, refetch } = useQuery(
    'users',
    async () => {
      const response = await api.get<User[]>('/admin/users')
      return response.data
    }
  )

  // ユーザー作成
  const createUserMutation = useMutation(
    async (userData: UserCreate) => {
      const response = await api.post('/admin/users', userData)
      return response.data
    },
    {
      onSuccess: () => {
        toast.success('ユーザーを作成しました')
        queryClient.invalidateQueries('users')
        setShowCreateModal(false)
        setFormData({ email: '', password: '', is_admin: false })
      },
      onError: (error: any) => {
        toast.error(`ユーザー作成に失敗しました: ${error.response?.data?.detail || error.message}`)
      }
    }
  )

  // ユーザー更新
  const updateUserMutation = useMutation(
    async ({ userId, updates }: { userId: string; updates: UserUpdate }) => {
      const response = await api.put(`/admin/users/${userId}`, updates)
      return response.data
    },
    {
      onSuccess: () => {
        toast.success('ユーザーを更新しました')
        queryClient.invalidateQueries('users')
        setShowEditModal(false)
        setSelectedUser(null)
      },
      onError: (error: any) => {
        toast.error(`ユーザー更新に失敗しました: ${error.response?.data?.detail || error.message}`)
      }
    }
  )

  // ユーザー削除
  const deleteUserMutation = useMutation(
    async (userId: string) => {
      await api.delete(`/admin/users/${userId}`)
    },
    {
      onSuccess: () => {
        toast.success('ユーザーを削除しました')
        queryClient.invalidateQueries('users')
      },
      onError: (error: any) => {
        toast.error(`ユーザー削除に失敗しました: ${error.response?.data?.detail || error.message}`)
      }
    }
  )

  const handleCreateUser = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.email || !formData.password) {
      toast.error('メールアドレスとパスワードを入力してください')
      return
    }
    createUserMutation.mutate(formData)
  }

  const handleEditUser = (user: User) => {
    setSelectedUser(user)
    setShowEditModal(true)
  }

  const handleUpdateUser = (field: keyof UserUpdate, value: any) => {
    if (!selectedUser) return
    updateUserMutation.mutate({
      userId: selectedUser.id,
      updates: { [field]: value }
    })
  }

  const handleDeleteUser = (user: User) => {
    if (user.id === currentUser?.id) {
      toast.error('自分自身を削除することはできません')
      return
    }
    
    if (confirm(`${user.email} を削除しますか？この操作は取り消せません。`)) {
      deleteUserMutation.mutate(user.id)
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ja-JP', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center">
            <Users className="w-8 h-8 mr-3" />
            ユーザー管理
          </h1>
          <p className="mt-2 text-gray-600">
            システムユーザーの管理・権限設定を行います
            {users && ` (${users.length}人)`}
          </p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => refetch()}
            className="btn-secondary flex items-center"
            disabled={isLoading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            更新
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary flex items-center"
          >
            <Plus className="w-4 h-4 mr-2" />
            ユーザー追加
          </button>
        </div>
      </div>

      {/* ユーザー一覧 */}
      {isLoading ? (
        <div className="text-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-primary-600 mb-4" />
          <p className="text-gray-600">ユーザー一覧を読み込み中...</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-red-800">ユーザー一覧の読み込みに失敗しました</p>
          <button
            onClick={() => refetch()}
            className="mt-2 btn-secondary"
          >
            再試行
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    ユーザー
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    権限
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    ステータス
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    作成日
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {users?.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10">
                          <div className="h-10 w-10 rounded-full bg-primary-100 flex items-center justify-center">
                            <User className="h-5 w-5 text-primary-600" />
                          </div>
                        </div>
                        <div className="ml-4">
                          <div className="text-sm font-medium text-gray-900 flex items-center">
                            <Mail className="w-4 h-4 mr-2 text-gray-400" />
                            {user.email}
                            {user.id === currentUser?.id && (
                              <span className="ml-2 px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full">
                                あなた
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        user.is_admin 
                          ? 'bg-purple-100 text-purple-800' 
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        <Shield className="w-3 h-3 mr-1" />
                        {user.is_admin ? '管理者' : '一般ユーザー'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        user.is_active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {user.is_active ? '有効' : '無効'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center">
                        <Calendar className="w-4 h-4 mr-1" />
                        {formatDate(user.created_at)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => handleEditUser(user)}
                          className="text-primary-600 hover:text-primary-900 p-1 rounded"
                          title="編集"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        {user.id !== currentUser?.id && (
                          <button
                            onClick={() => handleDeleteUser(user)}
                            className="text-red-600 hover:text-red-900 p-1 rounded"
                            title="削除"
                            disabled={deleteUserMutation.isLoading}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ユーザー作成モーダル */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
            <div className="flex justify-between items-center p-6 border-b">
              <h2 className="text-xl font-semibold">新しいユーザーを追加</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="p-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    メールアドレス
                  </label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    className="input-field"
                    placeholder="user@example.com"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    パスワード
                  </label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    className="input-field"
                    placeholder="パスワードを入力"
                    required
                    minLength={6}
                  />
                </div>
                <div>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.is_admin}
                      onChange={(e) => setFormData({...formData, is_admin: e.target.checked})}
                      className="form-checkbox text-primary-600"
                    />
                    <span className="ml-2 text-sm text-gray-700">管理者権限を付与</span>
                  </label>
                </div>
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn-secondary"
                >
                  キャンセル
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={createUserMutation.isLoading}
                >
                  {createUserMutation.isLoading ? '作成中...' : '作成'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ユーザー編集モーダル */}
      {showEditModal && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
            <div className="flex justify-between items-center p-6 border-b">
              <h2 className="text-xl font-semibold">ユーザー権限を編集</h2>
              <button
                onClick={() => setShowEditModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    メールアドレス
                  </label>
                  <input
                    type="text"
                    value={selectedUser.email}
                    disabled
                    className="input-field bg-gray-50"
                  />
                </div>
                <div className="space-y-3">
                  <label className="block text-sm font-medium text-gray-700">
                    権限設定
                  </label>
                  <div className="space-y-2">
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={selectedUser.is_active}
                        onChange={(e) => handleUpdateUser('is_active', e.target.checked)}
                        className="form-checkbox text-primary-600"
                        disabled={selectedUser.id === currentUser?.id}
                      />
                      <span className="ml-2 text-sm text-gray-700">アカウント有効</span>
                    </label>
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={selectedUser.is_admin}
                        onChange={(e) => handleUpdateUser('is_admin', e.target.checked)}
                        className="form-checkbox text-primary-600"
                        disabled={selectedUser.id === currentUser?.id}
                      />
                      <span className="ml-2 text-sm text-gray-700">管理者権限</span>
                    </label>
                  </div>
                  {selectedUser.id === currentUser?.id && (
                    <p className="text-xs text-gray-500">
                      ※ 自分自身の権限は変更できません
                    </p>
                  )}
                </div>
              </div>
              <div className="flex justify-end mt-6">
                <button
                  onClick={() => setShowEditModal(false)}
                  className="btn-primary"
                >
                  完了
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default UserManagement
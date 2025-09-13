import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { 
  Settings as SettingsIcon, Key, Database, Bot, Shield, 
  Save, RefreshCw, Eye, EyeOff, Check, X 
} from 'lucide-react'
import api from '../services/api'
import toast from 'react-hot-toast'
import { useAuth } from '../contexts/AuthContext'

interface SystemSettings {
  anthropic_api_key: string
  default_scraping_delay: number
  max_concurrent_requests: number
  default_report_template: string
  enable_auto_tagging: boolean
  max_content_length: number
  session_timeout_minutes: number
  enable_user_registration: boolean
}

const Settings: React.FC = () => {
  const { isAdmin } = useAuth()
  const queryClient = useQueryClient()
  const [showApiKey, setShowApiKey] = useState(false)
  const [settings, setSettings] = useState<SystemSettings>({
    anthropic_api_key: '',
    default_scraping_delay: 1.0,
    max_concurrent_requests: 5,
    default_report_template: 'summary',
    enable_auto_tagging: true,
    max_content_length: 50000,
    session_timeout_minutes: 1440,
    enable_user_registration: false
  })
  const [hasChanges, setHasChanges] = useState(false)

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

  // 設定値取得
  const { data: currentSettings, isLoading, error, refetch } = useQuery(
    'system-settings',
    async () => {
      const response = await api.get<SystemSettings>('/admin/settings')
      return response.data
    },
    {
      onSuccess: (data) => {
        setSettings(data)
        setHasChanges(false)
      }
    }
  )

  // 設定値更新
  const updateSettingsMutation = useMutation(
    async (settingsData: Partial<SystemSettings>) => {
      const response = await api.put('/admin/settings', settingsData)
      return response.data
    },
    {
      onSuccess: () => {
        toast.success('設定を保存しました')
        queryClient.invalidateQueries('system-settings')
        setHasChanges(false)
      },
      onError: (error: any) => {
        toast.error(`設定の保存に失敗しました: ${error.response?.data?.detail || error.message}`)
      }
    }
  )

  // API接続テスト
  const testApiConnectionMutation = useMutation(
    async () => {
      const response = await api.post('/admin/test-api-connection')
      return response.data
    },
    {
      onSuccess: (data) => {
        toast.success(`API接続成功: ${data.model || 'Claude API'}`)
      },
      onError: (error: any) => {
        toast.error(`API接続失敗: ${error.response?.data?.detail || error.message}`)
      }
    }
  )

  const handleSettingChange = (key: keyof SystemSettings, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }))
    setHasChanges(true)
  }

  const handleSave = () => {
    updateSettingsMutation.mutate(settings)
  }

  const handleReset = () => {
    if (currentSettings) {
      setSettings(currentSettings)
      setHasChanges(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center">
            <SettingsIcon className="w-8 h-8 mr-3" />
            システム設定
          </h1>
          <p className="mt-2 text-gray-600">
            システムの動作設定・API設定を行います
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
          {hasChanges && (
            <>
              <button
                onClick={handleReset}
                className="btn-secondary flex items-center"
              >
                <X className="w-4 h-4 mr-2" />
                リセット
              </button>
              <button
                onClick={handleSave}
                className="btn-primary flex items-center"
                disabled={updateSettingsMutation.isLoading}
              >
                <Save className="w-4 h-4 mr-2" />
                {updateSettingsMutation.isLoading ? '保存中...' : '保存'}
              </button>
            </>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-primary-600 mb-4" />
          <p className="text-gray-600">設定を読み込み中...</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-red-800">設定の読み込みに失敗しました</p>
          <button
            onClick={() => refetch()}
            className="mt-2 btn-secondary"
          >
            再試行
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* AI設定 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <Bot className="w-5 h-5 mr-2" />
              AI・LLM設定
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Key className="w-4 h-4 inline mr-1" />
                  Anthropic API Key
                </label>
                <div className="relative">
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    value={settings.anthropic_api_key}
                    onChange={(e) => handleSettingChange('anthropic_api_key', e.target.value)}
                    className="input-field pr-20"
                    placeholder="sk-ant-..."
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute inset-y-0 right-12 flex items-center px-2 text-gray-500 hover:text-gray-700"
                  >
                    {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                  <button
                    onClick={() => testApiConnectionMutation.mutate()}
                    disabled={!settings.anthropic_api_key || testApiConnectionMutation.isLoading}
                    className="absolute inset-y-0 right-2 flex items-center px-2 text-primary-600 hover:text-primary-800 disabled:text-gray-400"
                    title="接続テスト"
                  >
                    <Check className={`w-4 h-4 ${testApiConnectionMutation.isLoading ? 'animate-pulse' : ''}`} />
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Claude APIを使用するためのAPIキーを設定してください
                </p>
              </div>

              <div>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={settings.enable_auto_tagging}
                    onChange={(e) => handleSettingChange('enable_auto_tagging', e.target.checked)}
                    className="form-checkbox text-primary-600"
                  />
                  <span className="ml-2 text-sm text-gray-700">自動タグ生成を有効にする</span>
                </label>
                <p className="text-xs text-gray-500 mt-1 ml-6">
                  記事スクレイピング時にAIによる自動タグ付けを行います
                </p>
              </div>
            </div>
          </div>

          {/* スクレイピング設定 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <Database className="w-5 h-5 mr-2" />
              スクレイピング設定
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  リクエスト間隔（秒）
                </label>
                <input
                  type="number"
                  min="0.1"
                  max="10"
                  step="0.1"
                  value={settings.default_scraping_delay}
                  onChange={(e) => handleSettingChange('default_scraping_delay', parseFloat(e.target.value))}
                  className="input-field"
                />
                <p className="text-xs text-gray-500 mt-1">
                  サーバー負荷軽減のためのリクエスト間隔
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  最大同時リクエスト数
                </label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={settings.max_concurrent_requests}
                  onChange={(e) => handleSettingChange('max_concurrent_requests', parseInt(e.target.value))}
                  className="input-field"
                />
                <p className="text-xs text-gray-500 mt-1">
                  並列実行する最大スクレイピング数
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  最大コンテンツ長（文字数）
                </label>
                <input
                  type="number"
                  min="1000"
                  max="100000"
                  step="1000"
                  value={settings.max_content_length}
                  onChange={(e) => handleSettingChange('max_content_length', parseInt(e.target.value))}
                  className="input-field"
                />
                <p className="text-xs text-gray-500 mt-1">
                  記事コンテンツの最大保存文字数
                </p>
              </div>
            </div>
          </div>

          {/* レポート設定 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              レポート・分析設定
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  デフォルトレポートテンプレート
                </label>
                <select
                  value={settings.default_report_template}
                  onChange={(e) => handleSettingChange('default_report_template', e.target.value)}
                  className="input-field"
                >
                  <option value="summary">要約レポート</option>
                  <option value="tag_analysis">タグ分析</option>
                  <option value="source_analysis">ソース分析</option>
                  <option value="trend_analysis">トレンド分析</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  レポート作成時のデフォルトテンプレート
                </p>
              </div>
            </div>
          </div>

          {/* セキュリティ設定 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <Shield className="w-5 h-5 mr-2" />
              セキュリティ設定
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  セッションタイムアウト（分）
                </label>
                <input
                  type="number"
                  min="30"
                  max="10080"
                  value={settings.session_timeout_minutes}
                  onChange={(e) => handleSettingChange('session_timeout_minutes', parseInt(e.target.value))}
                  className="input-field"
                />
                <p className="text-xs text-gray-500 mt-1">
                  ログインセッションの有効期限（30分〜7日）
                </p>
              </div>

              <div>
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={settings.enable_user_registration}
                    onChange={(e) => handleSettingChange('enable_user_registration', e.target.checked)}
                    className="form-checkbox text-primary-600"
                  />
                  <span className="ml-2 text-sm text-gray-700">ユーザー登録を有効にする</span>
                </label>
                <p className="text-xs text-gray-500 mt-1 ml-6">
                  新規ユーザーの登録を許可します（現在は管理者のみが追加可能）
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 保存確認 */}
      {hasChanges && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <RefreshCw className="h-5 w-5 text-yellow-400" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-yellow-800">
                設定が変更されています
              </h3>
              <div className="mt-2 text-sm text-yellow-700">
                <p>変更を保存するか、リセットしてください。</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Settings
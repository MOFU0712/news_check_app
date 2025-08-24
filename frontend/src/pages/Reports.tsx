import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { 
  BarChart3, TrendingUp, FileText, Calendar, 
  Tag, Globe, RefreshCw, Save, Edit, Trash2, Eye, Download, Archive
} from 'lucide-react'
import api from '../services/api'
import toast from 'react-hot-toast'

interface ReportData {
  report_type: string
  generated_at: string
  data: any
  summary: string
}

interface AnalyticsOverview {
  period: {
    days: number
    start_date: string
    end_date: string
  }
  statistics: {
    total_articles: number
    period_articles: number
    daily_average: number
  }
  daily_data: Record<string, number>
  top_tags: Array<[string, number]>
  top_sources: Array<[string, number]>
}

interface SavedReport {
  id: string
  title: string
  report_type: string
  content: string
  summary?: string
  tags?: string[]
  created_at: string
  updated_at: string
}

interface TechnicalReportRequest {
  keyword: string
  start_date?: string
  end_date?: string
  max_articles: number
  template_id?: string
}

interface TechnicalReportResponse {
  keyword: string
  content: string
  articles_count: number
  generated_at: string
}

interface PromptTemplate {
  id: string
  name: string
  description?: string
  template_type: string
  system_prompt: string
  user_prompt_template?: string
  model_name: string
  max_tokens: number
  temperature: number
  created_at: string
  updated_at: string
}

const Reports: React.FC = () => {
  const queryClient = useQueryClient()
  const [reportType, setReportType] = useState<string>('summary')
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0]
  })
  const [selectedTags] = useState<string[]>([])
  const [selectedSources] = useState<string[]>([])
  const [, setAnalyticsData] = useState<AnalyticsOverview | null>(null)
  const [reportTitle, setReportTitle] = useState('')
  const [currentView, setCurrentView] = useState<'create' | 'technical' | 'saved'>('create')
  const [selectedReport, setSelectedReport] = useState<SavedReport | null>(null)
  const [editingReport, setEditingReport] = useState<SavedReport | null>(null)
  const [selectedPromptTemplate, setSelectedPromptTemplate] = useState<string | null>(null)
  const [showPromptEditor, setShowPromptEditor] = useState(false)
  const [editingPromptTemplate, setEditingPromptTemplate] = useState<PromptTemplate | null>(null)
  const [selectedReportIds, setSelectedReportIds] = useState<string[]>([])
  const [isExporting, setIsExporting] = useState(false)
  
  // 技術まとめレポート用State
  const [technicalKeyword, setTechnicalKeyword] = useState('')
  const [technicalMaxArticles, setTechnicalMaxArticles] = useState(20)
  const [technicalDateRange, setTechnicalDateRange] = useState({ start: '', end: '' })
  const [technicalTemplateId, setTechnicalTemplateId] = useState('')
  const [technicalReportContent, setTechnicalReportContent] = useState('')
  const [technicalArticlesCount, setTechnicalArticlesCount] = useState(0)

  // レポート生成
  const generateReport = async () => {
    const response = await api.post<ReportData>('/reports/generate', {
      report_type: reportType,
      start_date: dateRange.start,
      end_date: dateRange.end,
      tags: selectedTags.length > 0 ? selectedTags : undefined,
      sources: selectedSources.length > 0 ? selectedSources : undefined
    })
    return response.data
  }

  // レポート生成・保存
  const generateAndSaveReport = async () => {
    if (!reportTitle.trim()) {
      toast.error('レポートタイトルを入力してください')
      return
    }

    const response = await api.post<SavedReport>('/reports/generate-and-save', {
      report_type: reportType,
      start_date: dateRange.start,
      end_date: dateRange.end,
      tags: selectedTags.length > 0 ? selectedTags : undefined,
      sources: selectedSources.length > 0 ? selectedSources : undefined,
      title: reportTitle,
      save_as_blog: true,
      prompt_template_id: selectedPromptTemplate
    })
    return response.data
  }

  // 技術まとめレポート生成
  const generateTechnicalReport = async (): Promise<TechnicalReportResponse> => {
    if (!technicalKeyword.trim()) {
      throw new Error('キーワードを入力してください')
    }

    const request: TechnicalReportRequest = {
      keyword: technicalKeyword,
      max_articles: technicalMaxArticles,
      ...(technicalDateRange.start && { start_date: technicalDateRange.start }),
      ...(technicalDateRange.end && { end_date: technicalDateRange.end }),
      ...(technicalTemplateId && { template_id: technicalTemplateId })
    }

    const response = await api.post<TechnicalReportResponse>('/reports/technical-summary', request)
    return response.data
  }

  // 生成済みの技術まとめレポートを保存
  const saveTechnicalReport = async () => {
    if (!technicalReportContent || !technicalKeyword.trim()) {
      toast.error('保存するレポートがありません')
      return
    }

    const request = {
      title: `技術まとめ: ${technicalKeyword}`,
      content: technicalReportContent,
      report_type: "technical_summary",
      summary: `「${technicalKeyword}」に関する技術まとめレポート（${technicalArticlesCount}件の記事を分析）`,
      tags: [technicalKeyword, "技術まとめ", "technical_summary"]
    }

    const response = await api.post('/reports/saved', request)
    return response.data
  }

  const { data: reportData, isLoading: reportLoading, refetch: generateNewReport } = useQuery(
    ['report', reportType, dateRange, selectedTags, selectedSources],
    generateReport,
    {
      enabled: false, // 手動でトリガー
    }
  )

  // 保存されたレポート一覧を取得
  const { data: savedReports, isLoading: savedReportsLoading } = useQuery(
    'saved-reports',
    async () => {
      const response = await api.get<SavedReport[]>('/reports/saved')
      return response.data
    }
  )

  // プロンプトテンプレート一覧を取得
  const { data: promptTemplates } = useQuery(
    'prompt-templates',
    async () => {
      const response = await api.get<PromptTemplate[]>('/prompt-templates?template_type=blog_report')
      return response.data
    }
  )

  // 技術まとめ用プロンプトテンプレート一覧を取得
  const { data: technicalTemplates, isLoading: technicalTemplatesLoading } = useQuery(
    'technical-prompt-templates',
    async () => {
      console.log('Fetching technical templates...')
      const response = await api.get<PromptTemplate[]>('/prompt-templates?template_type=technical_summary')
      console.log('Technical templates response:', response.data)
      return response.data
    },
    {
      onError: (error) => {
        console.error('Error fetching technical templates:', error)
      }
    }
  )

  // 全プロンプトテンプレート一覧を取得（モーダル表示用）
  const { data: allPromptTemplates } = useQuery(
    'all-prompt-templates',
    async () => {
      const response = await api.get<PromptTemplate[]>('/prompt-templates')
      return response.data
    }
  )

  // レポート保存
  const saveReportMutation = useMutation(generateAndSaveReport, {
    onSuccess: () => {
      toast.success('レポートを保存しました')
      queryClient.invalidateQueries('saved-reports')
      setReportTitle('')
      setCurrentView('saved')
    },
    onError: () => {
      toast.error('レポートの保存に失敗しました')
    }
  })

  // レポート削除
  const deleteReportMutation = useMutation(
    async (reportId: string) => {
      await api.delete(`/reports/saved/${reportId}`)
    },
    {
      onSuccess: () => {
        toast.success('レポートを削除しました')
        queryClient.invalidateQueries('saved-reports')
        if (selectedReport) {
          setSelectedReport(null)
        }
      },
      onError: () => {
        toast.error('レポートの削除に失敗しました')
      }
    }
  )

  // 技術まとめレポート生成
  const technicalReportMutation = useMutation(generateTechnicalReport, {
    onSuccess: (data) => {
      setTechnicalReportContent(data.content)
      setTechnicalArticlesCount(data.articles_count)
      toast.success(`技術まとめレポートを生成しました（${data.articles_count}件の記事を分析）`)
    },
    onError: (error: any) => {
      const message = error?.response?.data?.detail || 'レポートの生成に失敗しました'
      toast.error(message)
    }
  })

  // 技術まとめレポート保存
  const saveTechnicalReportMutation = useMutation(saveTechnicalReport, {
    onSuccess: () => {
      toast.success('技術まとめレポートを保存しました')
      queryClient.invalidateQueries('saved-reports')
      setCurrentView('saved')
      // リセット
      setTechnicalKeyword('')
      setTechnicalReportContent('')
      setTechnicalArticlesCount(0)
    },
    onError: (error: any) => {
      const message = error?.response?.data?.detail || 'レポートの保存に失敗しました'
      toast.error(message)
    }
  })

  // 分析概要を取得
  const { data: analytics } = useQuery(
    'analytics-overview',
    async () => {
      const response = await api.get<AnalyticsOverview>('/reports/analytics/overview?days=30')
      setAnalyticsData(response.data)
      return response.data
    },
    {
      staleTime: 5 * 60 * 1000, // 5分間キャッシュ
    }
  )

  // 単一レポートエクスポート
  const exportReportAsMarkdown = async (reportId: string) => {
    try {
      setIsExporting(true)
      console.log(`Exporting report: ${reportId}`)
      
      const response = await fetch(`/api/reports/saved/${reportId}/export/markdown`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Accept': 'text/markdown'
        }
      })
      
      console.log(`Response status: ${response.status}`)
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error(`Export error: ${errorText}`)
        throw new Error(`エクスポートに失敗しました (${response.status}): ${errorText}`)
      }
      
      const blob = await response.blob()
      console.log(`Blob size: ${blob.size}`)
      
      const contentDisposition = response.headers.get('Content-Disposition')
      let filename = `report_${reportId}_${new Date().getTime()}.md`
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename\*?=(?:UTF-8'')?([^;]+)/);
        if (filenameMatch) {
          filename = decodeURIComponent(filenameMatch[1].replace(/['"]/g, ''))
        }
      }
      
      console.log(`Download filename: ${filename}`)
      
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style.display = 'none'
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      toast.success('レポートをエクスポートしました')
    } catch (error: any) {
      console.error('Export error:', error)
      toast.error(`エクスポートに失敗しました: ${error.message}`)
    } finally {
      setIsExporting(false)
    }
  }

  // 複数レポート一括エクスポート
  const exportMultipleReportsAsMarkdown = async () => {
    if (selectedReportIds.length === 0) {
      toast.error('エクスポートするレポートを選択してください')
      return
    }
    
    try {
      setIsExporting(true)
      const response = await fetch('/api/reports/export/markdown/bulk', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(selectedReportIds)
      })
      
      if (!response.ok) {
        throw new Error('一括エクスポートに失敗しました')
      }
      
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style.display = 'none'
      a.href = url
      a.download = `reports_${new Date().getTime()}.zip`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      toast.success(`${selectedReportIds.length}件のレポートをエクスポートしました`)
      setSelectedReportIds([])
    } catch (error) {
      toast.error('一括エクスポートに失敗しました')
    } finally {
      setIsExporting(false)
    }
  }

  // レポート選択の切り替え
  const toggleReportSelection = (reportId: string) => {
    setSelectedReportIds(prev => 
      prev.includes(reportId) 
        ? prev.filter(id => id !== reportId)
        : [...prev, reportId]
    )
  }

  // 全選択/全解除の切り替え
  const toggleAllReportsSelection = () => {
    if (savedReports) {
      if (selectedReportIds.length === savedReports.length) {
        setSelectedReportIds([])
      } else {
        setSelectedReportIds(savedReports.map(report => report.id))
      }
    }
  }

  const reportTypes = [
    { value: 'summary', label: '概要レポート', icon: FileText },
    { value: 'tag_analysis', label: 'タグ分析', icon: Tag },
    { value: 'source_analysis', label: 'ソース分析', icon: Globe },
    { value: 'trend_analysis', label: 'トレンド分析', icon: TrendingUp }
  ]

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">レポート・分析</h1>
        <p className="mt-2 text-gray-600">
          記事データの分析とレポート生成機能
        </p>
        
        {/* タブ */}
        <div className="mt-6">
          <nav className="flex space-x-1 bg-gray-100 p-1 rounded-lg">
            <button
              onClick={() => setCurrentView('create')}
              className={`flex items-center px-4 py-3 rounded-md font-semibold text-sm transition-all duration-200 ${
                currentView === 'create'
                  ? 'bg-white text-primary-700 shadow-sm ring-1 ring-primary-200'
                  : 'text-gray-600 hover:text-gray-800 hover:bg-white/50'
              }`}
            >
              <FileText className="w-4 h-4 mr-2" />
              レポート作成
            </button>
            <button
              onClick={() => setCurrentView('technical')}
              className={`flex items-center px-4 py-3 rounded-md font-semibold text-sm transition-all duration-200 ${
                currentView === 'technical'
                  ? 'bg-white text-primary-700 shadow-sm ring-1 ring-primary-200'
                  : 'text-gray-600 hover:text-gray-800 hover:bg-white/50'
              }`}
            >
              <BarChart3 className="w-4 h-4 mr-2" />
              技術まとめ
            </button>
            <button
              onClick={() => {
                setCurrentView('saved')
                setSelectedReportIds([]) // タブ切り替え時に選択をリセット
              }}
              className={`flex items-center px-4 py-3 rounded-md font-semibold text-sm transition-all duration-200 ${
                currentView === 'saved'
                  ? 'bg-white text-primary-700 shadow-sm ring-1 ring-primary-200'
                  : 'text-gray-600 hover:text-gray-800 hover:bg-white/50'
              }`}
            >
              <Archive className="w-4 h-4 mr-2" />
              保存済みレポート
              {savedReports && savedReports.length > 0 && (
                <span className="ml-2 bg-primary-100 text-primary-700 px-2 py-0.5 rounded-full text-xs font-medium">
                  {savedReports.length}
                </span>
              )}
            </button>
          </nav>
        </div>
      </div>

      {/* 分析概要カード */}
      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white p-6 rounded-lg shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">総記事数</p>
                <p className="text-2xl font-bold text-gray-900">
                  {analytics.statistics.total_articles.toLocaleString()}
                </p>
              </div>
              <FileText className="h-8 w-8 text-blue-600" />
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">今月の記事</p>
                <p className="text-2xl font-bold text-gray-900">
                  {analytics.statistics.period_articles}
                </p>
              </div>
              <TrendingUp className="h-8 w-8 text-green-600" />
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">1日平均</p>
                <p className="text-2xl font-bold text-gray-900">
                  {analytics.statistics.daily_average}
                </p>
              </div>
              <BarChart3 className="h-8 w-8 text-purple-600" />
            </div>
          </div>

          <div className="bg-white p-6 rounded-lg shadow border">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">人気タグ</p>
                <p className="text-2xl font-bold text-gray-900">
                  {analytics.top_tags.length}
                </p>
              </div>
              <Tag className="h-8 w-8 text-orange-600" />
            </div>
          </div>
        </div>
      )}

      {currentView === 'create' && (
        <div className="space-y-6">
          {/* レポート生成セクション */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold text-gray-900">カスタムレポート生成</h2>
              <div className="flex space-x-2">
                <button
                  onClick={() => generateNewReport()}
                  disabled={reportLoading || saveReportMutation.isLoading}
                  className="btn-secondary flex items-center"
                >
                  {reportLoading ? (
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <FileText className="w-4 h-4 mr-2" />
                  )}
                  プレビュー生成
                </button>
                <button
                  onClick={() => saveReportMutation.mutate()}
                  disabled={reportLoading || saveReportMutation.isLoading || !reportTitle.trim()}
                  className="btn-primary flex items-center"
                >
                  {saveReportMutation.isLoading ? (
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4 mr-2" />
                  )}
                  保存
                </button>
              </div>
            </div>

            {/* レポート設定 */}
            <div className="space-y-6 mb-6">
              {/* タイトル */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  レポートタイトル
                </label>
                <input
                  type="text"
                  value={reportTitle}
                  onChange={(e) => setReportTitle(e.target.value)}
                  className="input-field"
                  placeholder="レポートのタイトルを入力"
                />
              </div>

              {/* プロンプトテンプレート選択 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  プロンプトテンプレート
                  <button
                    onClick={() => setShowPromptEditor(true)}
                    className="ml-2 text-sm text-primary-600 hover:text-primary-800"
                  >
                    編集・管理
                  </button>
                </label>
                <select
                  value={selectedPromptTemplate || ''}
                  onChange={(e) => setSelectedPromptTemplate(e.target.value || null)}
                  className="input-field"
                >
                  <option value="">デフォルトプロンプトを使用</option>
                  {promptTemplates?.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name} ({template.model_name})
                    </option>
                  ))}
                </select>
                {selectedPromptTemplate && promptTemplates && (
                  <div className="mt-2 p-3 bg-gray-50 rounded-md">
                    <div className="text-xs text-gray-600">
                      {promptTemplates.find(t => t.id === selectedPromptTemplate)?.description || 'カスタムプロンプトテンプレート'}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* レポートタイプ */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              レポートタイプ
            </label>
            <div className="space-y-2">
              {reportTypes.map((type) => {
                const IconComponent = type.icon
                return (
                  <label key={type.value} className="flex items-center">
                    <input
                      type="radio"
                      name="reportType"
                      value={type.value}
                      checked={reportType === type.value}
                      onChange={(e) => setReportType(e.target.value)}
                      className="form-radio text-primary-600"
                    />
                    <IconComponent className="w-4 h-4 ml-2 mr-1" />
                    <span className="text-sm">{type.label}</span>
                  </label>
                )
              })}
            </div>
          </div>

          {/* 日付範囲 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              <Calendar className="w-4 h-4 inline mr-1" />
              分析期間
            </label>
            <div className="space-y-2">
              <input
                type="date"
                value={dateRange.start}
                onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
                className="input-field"
              />
              <input
                type="date"
                value={dateRange.end}
                onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
                className="input-field"
              />
            </div>
          </div>
        </div>

        {/* レポート結果 */}
        {reportData && (
          <div className="border-t pt-6">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <h3 className="font-semibold text-blue-900 mb-2">
                {reportTypes.find(t => t.value === reportData.report_type)?.label} レポート結果
              </h3>
              <p className="text-blue-800 text-sm mb-2">
                生成日時: {new Date(reportData.generated_at).toLocaleString('ja-JP')}
              </p>
              <p className="text-blue-800">{reportData.summary}</p>
            </div>

            {/* データ詳細 */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h4 className="font-medium text-gray-900 mb-2">詳細データ</h4>
              <pre className="text-sm text-gray-600 overflow-x-auto max-h-64 break-all whitespace-pre-wrap">
                {JSON.stringify(reportData.data, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* 人気タグ・ソース */}
      {analytics && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* 人気タグ */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <Tag className="w-5 h-5 mr-2" />
              人気タグ（過去30日）
            </h3>
            <div className="space-y-2">
              {analytics.top_tags.slice(0, 10).map(([tag, count], index) => (
                <div key={tag} className="flex items-center justify-between">
                  <span className="text-sm text-gray-700">
                    {index + 1}. {tag}
                  </span>
                  <span className="text-sm font-medium text-gray-900">
                    {count}件
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* 人気ソース */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
              <Globe className="w-5 h-5 mr-2" />
              人気ソース（過去30日）
            </h3>
            <div className="space-y-2">
              {analytics.top_sources.slice(0, 10).map(([source, count], index) => (
                <div key={source} className="flex items-center justify-between">
                  <span className="text-sm text-gray-700 truncate">
                    {index + 1}. {source}
                  </span>
                  <span className="text-sm font-medium text-gray-900">
                    {count}件
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      </div>
      )}

      {/* 技術まとめレポート */}
      {currentView === 'technical' && (
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-lg shadow">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">技術まとめレポート</h2>
            <p className="text-sm text-gray-600 mb-6">
              特定のキーワードに関連する記事を分析して、技術的なまとめレポートを生成します。
            </p>
            
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 設定フォーム */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    キーワード *
                  </label>
                  <input
                    type="text"
                    value={technicalKeyword}
                    onChange={(e) => setTechnicalKeyword(e.target.value)}
                    placeholder="例: React, Docker, AI など"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      開始日
                    </label>
                    <input
                      type="date"
                      value={technicalDateRange.start}
                      onChange={(e) => setTechnicalDateRange({...technicalDateRange, start: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      終了日
                    </label>
                    <input
                      type="date"
                      value={technicalDateRange.end}
                      onChange={(e) => setTechnicalDateRange({...technicalDateRange, end: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
                    />
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    最大記事数
                  </label>
                  <input
                    type="number"
                    value={technicalMaxArticles}
                    onChange={(e) => setTechnicalMaxArticles(parseInt(e.target.value) || 20)}
                    min="1"
                    max="50"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    プロンプトテンプレート
                    <button
                      onClick={() => setShowPromptEditor(true)}
                      className="ml-2 text-sm text-primary-600 hover:text-primary-800"
                    >
                      編集・管理
                    </button>
                  </label>
                  <select
                    value={technicalTemplateId}
                    onChange={(e) => setTechnicalTemplateId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
                    disabled={technicalTemplatesLoading}
                  >
                    <option value="">
                      {technicalTemplatesLoading ? '読み込み中...' : 'デフォルト'}
                    </option>
                    {technicalTemplates?.map(template => (
                      <option key={template.id} value={template.id}>
                        {template.name}
                      </option>
                    ))}
                  </select>
                  {!technicalTemplatesLoading && technicalTemplates?.length === 0 && (
                    <div className="mt-1 text-sm text-gray-500">
                      技術まとめ用のテンプレートがありません
                    </div>
                  )}
                  {technicalTemplateId && technicalTemplates && (
                    <div className="mt-2 p-3 bg-gray-50 rounded-md">
                      <div className="text-xs text-gray-600">
                        {technicalTemplates.find(t => t.id === technicalTemplateId)?.description || 'カスタムプロンプトテンプレート'}
                      </div>
                    </div>
                  )}
                </div>
                
                <div className="flex space-x-3">
                  <button
                    onClick={() => technicalReportMutation.mutate()}
                    disabled={technicalReportMutation.isLoading || !technicalKeyword.trim()}
                    className="flex-1 bg-primary-600 text-white px-4 py-2 rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                  >
                    {technicalReportMutation.isLoading ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        生成中...
                      </>
                    ) : (
                      <>
                        <FileText className="w-4 h-4 mr-2" />
                        レポート生成
                      </>
                    )}
                  </button>
                  
                  {technicalReportContent && (
                    <button
                      onClick={() => saveTechnicalReportMutation.mutate()}
                      disabled={saveTechnicalReportMutation.isLoading}
                      className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                    >
                      {saveTechnicalReportMutation.isLoading ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <Save className="w-4 h-4" />
                      )}
                    </button>
                  )}
                </div>
              </div>
              
              {/* プレビュー */}
              <div>
                {technicalReportContent ? (
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-medium text-gray-900">
                        生成結果 ({technicalArticlesCount}件の記事を分析)
                      </h3>
                    </div>
                    <div className="prose prose-sm max-w-none">
                      <div className="whitespace-pre-wrap text-sm text-gray-700 break-words overflow-x-hidden overflow-wrap-anywhere">
                        {technicalReportContent}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="bg-gray-50 p-4 rounded-lg text-center text-gray-500">
                    キーワードを入力してレポートを生成してください
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* 保存済みレポート一覧 */}
      {currentView === 'saved' && (
        <div className="space-y-6">
          {savedReportsLoading ? (
            <div className="flex justify-center items-center h-64">
              <RefreshCw className="w-8 h-8 animate-spin text-gray-500" />
              <span className="ml-2 text-gray-500">読み込み中...</span>
            </div>
          ) : (
            <>
              {savedReports && savedReports.length > 0 ? (
                <>
                  {/* エクスポートコントロール */}
                  <div className="bg-white rounded-lg shadow p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        <div className="flex items-center">
                          <input
                            type="checkbox"
                            checked={savedReports.length > 0 && selectedReportIds.length === savedReports.length}
                            onChange={toggleAllReportsSelection}
                            className="form-checkbox text-primary-600"
                          />
                          <span className="ml-2 text-sm text-gray-700">
                            全選択 ({selectedReportIds.length}/{savedReports.length})
                          </span>
                        </div>
                        {selectedReportIds.length > 0 && (
                          <span className="text-sm text-primary-600">
                            {selectedReportIds.length}件選択中
                          </span>
                        )}
                      </div>
                      
                      <div className="flex space-x-2">
                        <button
                          onClick={exportMultipleReportsAsMarkdown}
                          disabled={selectedReportIds.length === 0 || isExporting}
                          className="btn-secondary flex items-center text-sm disabled:opacity-50"
                        >
                          {isExporting ? (
                            <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                          ) : (
                            <Archive className="w-4 h-4 mr-1" />
                          )}
                          一括エクスポート (ZIP)
                        </button>
                      </div>
                    </div>
                  </div>
                  
                  {/* レポート一覧 */}
                  <div className="grid gap-6">
                    {savedReports.map((report) => (
                      <div key={report.id} className="bg-white rounded-lg shadow p-6">
                        <div className="flex justify-between items-start mb-4">
                          <div className="flex items-start space-x-3">
                            <input
                              type="checkbox"
                              checked={selectedReportIds.includes(report.id)}
                              onChange={() => toggleReportSelection(report.id)}
                              className="form-checkbox text-primary-600 mt-1"
                            />
                            <div>
                              <h3 className="text-lg font-semibold text-gray-900">{report.title}</h3>
                              <div className="flex items-center space-x-4 text-sm text-gray-500 mt-1">
                                <span>{reportTypes.find(t => t.value === report.report_type)?.label}</span>
                                <span>•</span>
                                <span>{new Date(report.created_at).toLocaleDateString('ja-JP')}</span>
                              </div>
                            </div>
                          </div>
                          <div className="flex space-x-2">
                            <button
                              onClick={() => exportReportAsMarkdown(report.id)}
                              disabled={isExporting}
                              className="btn-secondary flex items-center text-sm"
                              title="Markdownでエクスポート"
                            >
                              <Download className="w-4 h-4 mr-1" />
                              MD
                            </button>
                            <button
                              onClick={() => setSelectedReport(report)}
                              className="btn-secondary flex items-center text-sm"
                            >
                              <Eye className="w-4 h-4 mr-1" />
                              表示
                            </button>
                            <button
                              onClick={() => setEditingReport(report)}
                              className="btn-secondary flex items-center text-sm"
                            >
                              <Edit className="w-4 h-4 mr-1" />
                              編集
                            </button>
                            <button
                              onClick={() => {
                                if (confirm('このレポートを削除しますか？')) {
                                  deleteReportMutation.mutate(report.id)
                                }
                              }}
                              className="btn-danger flex items-center text-sm"
                              disabled={deleteReportMutation.isLoading}
                            >
                              <Trash2 className="w-4 h-4 mr-1" />
                              削除
                            </button>
                          </div>
                        </div>
                      
                      {report.summary && (
                        <p className="text-gray-600 text-sm mb-4">{report.summary}</p>
                      )}
                      
                      {report.tags && report.tags.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {report.tags.map((tag) => (
                            <span key={tag} className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                </>
              ) : (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">保存されたレポートがありません</h3>
                  <p className="text-gray-500 mb-4">まずはレポートを作成して保存してみましょう</p>
                  <button
                    onClick={() => setCurrentView('create')}
                    className="btn-primary"
                  >
                    レポートを作成
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
      
      {/* レポート表示モーダル */}
      {selectedReport && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b">
              <h2 className="text-xl font-semibold">{selectedReport.title}</h2>
              <button
                onClick={() => setSelectedReport(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-8rem)]">
              <div className="prose max-w-none break-words overflow-x-hidden">
                <div className="break-words overflow-wrap-anywhere" dangerouslySetInnerHTML={{ 
                  __html: selectedReport.content
                    .replace(/\n/g, '<br>')
                    .replace(/## (.*?)(\n|$)/g, '<h2>$1</h2>')
                    .replace(/### (.*?)(\n|$)/g, '<h3>$1</h3>')
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/^- (.*?)$/gm, '<li>$1</li>')
                    .replace(/<li>/g, '<ul><li>')
                    .replace(/<\/li>(?!\s*<li>)/g, '</li></ul>')
                }} />
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* レポート編集モーダル */}
      {editingReport && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b">
              <h2 className="text-xl font-semibold">レポート編集</h2>
              <button
                onClick={() => setEditingReport(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-8rem)]">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    タイトル
                  </label>
                  <input
                    type="text"
                    value={editingReport.title}
                    onChange={(e) => setEditingReport({...editingReport, title: e.target.value})}
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    コンテンツ
                  </label>
                  <textarea
                    value={editingReport.content}
                    onChange={(e) => setEditingReport({...editingReport, content: e.target.value})}
                    rows={20}
                    className="input-field font-mono text-sm resize-none overflow-x-auto"
                    style={{ wordBreak: 'break-word', overflowWrap: 'anywhere' }}
                  />
                </div>
                <div className="flex justify-end space-x-2 pt-4">
                  <button
                    onClick={() => setEditingReport(null)}
                    className="btn-secondary"
                  >
                    キャンセル
                  </button>
                  <button
                    onClick={async () => {
                      try {
                        await api.put(`/reports/saved/${editingReport.id}`, {
                          title: editingReport.title,
                          content: editingReport.content
                        })
                        toast.success('レポートを更新しました')
                        queryClient.invalidateQueries('saved-reports')
                        setEditingReport(null)
                      } catch (error) {
                        toast.error('レポートの更新に失敗しました')
                      }
                    }}
                    className="btn-primary"
                  >
                    保存
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* プロンプトテンプレート編集モーダル */}
      {showPromptEditor && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b">
              <h2 className="text-xl font-semibold">プロンプトテンプレート管理</h2>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => {
                    setEditingPromptTemplate({
                      id: '',
                      name: '',
                      description: '',
                      template_type: 'blog_report',
                      system_prompt: '',
                      user_prompt_template: '',
                      model_name: 'claude-sonnet-4-20250514',
                      max_tokens: 2000,
                      temperature: 0.3,
                      created_at: '',
                      updated_at: ''
                    })
                  }}
                  className="btn-secondary text-sm"
                >
                  レポート用作成
                </button>
                <button
                  onClick={() => {
                    setEditingPromptTemplate({
                      id: '',
                      name: '',
                      description: '',
                      template_type: 'technical_summary',
                      system_prompt: '',
                      user_prompt_template: '',
                      model_name: 'claude-sonnet-4-20250514',
                      max_tokens: 3000,
                      temperature: 0.3,
                      created_at: '',
                      updated_at: ''
                    })
                  }}
                  className="btn-primary text-sm"
                >
                  技術まとめ用作成
                </button>
                <button
                  onClick={() => setShowPromptEditor(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-8rem)]">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* テンプレート一覧 */}
                <div>
                  <h3 className="text-lg font-medium mb-4">保存済みテンプレート</h3>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {allPromptTemplates?.map((template) => (
                      <div
                        key={template.id}
                        className="p-3 border rounded-lg cursor-pointer hover:bg-gray-50"
                        onClick={() => setEditingPromptTemplate(template)}
                      >
                        <div className="flex items-center justify-between">
                          <div className="font-medium">{template.name}</div>
                          <span className={`text-xs px-2 py-1 rounded-full ${
                            template.template_type === 'technical_summary' 
                              ? 'bg-green-100 text-green-800' 
                              : 'bg-blue-100 text-blue-800'
                          }`}>
                            {template.template_type === 'technical_summary' ? '技術まとめ' : 'レポート'}
                          </span>
                        </div>
                        <div className="text-sm text-gray-600">{template.description}</div>
                        <div className="text-xs text-gray-400 mt-1">
                          {template.model_name} | {template.max_tokens}tokens | temp:{template.temperature}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* テンプレート編集 */}
                <div>
                  {editingPromptTemplate ? (
                    <div className="space-y-4">
                      <h3 className="text-lg font-medium">
                        {editingPromptTemplate.id ? 'テンプレート編集' : '新規テンプレート作成'}
                      </h3>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">名前</label>
                        <input
                          type="text"
                          value={editingPromptTemplate.name}
                          onChange={(e) => setEditingPromptTemplate({
                            ...editingPromptTemplate,
                            name: e.target.value
                          })}
                          className="input-field"
                          placeholder="テンプレート名"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">説明</label>
                        <input
                          type="text"
                          value={editingPromptTemplate.description || ''}
                          onChange={(e) => setEditingPromptTemplate({
                            ...editingPromptTemplate,
                            description: e.target.value
                          })}
                          className="input-field"
                          placeholder="テンプレートの説明"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">テンプレートタイプ</label>
                        <select
                          value={editingPromptTemplate.template_type}
                          onChange={(e) => setEditingPromptTemplate({
                            ...editingPromptTemplate,
                            template_type: e.target.value
                          })}
                          className="input-field"
                        >
                          <option value="blog_report">レポート用 (blog_report)</option>
                          <option value="technical_summary">技術まとめ用 (technical_summary)</option>
                        </select>
                      </div>
                      
                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">モデル</label>
                          <select
                            value={editingPromptTemplate.model_name}
                            onChange={(e) => setEditingPromptTemplate({
                              ...editingPromptTemplate,
                              model_name: e.target.value
                            })}
                            className="input-field text-sm"
                          >
                            <option value="claude-sonnet-4-20250514">Claude 4 Sonnet (最新・推奨)</option>
                            <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet (旧版)</option>
                            <option value="claude-3-haiku-20240307">Claude 3 Haiku (軽量版)</option>
                          </select>
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Max Tokens</label>
                          <input
                            type="number"
                            value={editingPromptTemplate.max_tokens}
                            onChange={(e) => setEditingPromptTemplate({
                              ...editingPromptTemplate,
                              max_tokens: parseInt(e.target.value)
                            })}
                            className="input-field text-sm"
                            min="500"
                            max="4000"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Temperature</label>
                          <input
                            type="number"
                            step="0.1"
                            value={editingPromptTemplate.temperature}
                            onChange={(e) => setEditingPromptTemplate({
                              ...editingPromptTemplate,
                              temperature: parseFloat(e.target.value)
                            })}
                            className="input-field text-sm"
                            min="0"
                            max="1"
                          />
                        </div>
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">システムプロンプト</label>
                        <textarea
                          value={editingPromptTemplate.system_prompt}
                          onChange={(e) => setEditingPromptTemplate({
                            ...editingPromptTemplate,
                            system_prompt: e.target.value
                          })}
                          rows={8}
                          className="input-field font-mono text-sm"
                          placeholder="システムプロンプトを入力..."
                        />
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          ユーザープロンプトテンプレート
                          <span className="text-xs text-gray-500 ml-1">
                            (オプション: {"{title}, {report_context}, {report_type}, {summary}, {content}, {data}, {datetime}"} が使用可能)
                          </span>
                        </label>
                        <textarea
                          value={editingPromptTemplate.user_prompt_template || ''}
                          onChange={(e) => setEditingPromptTemplate({
                            ...editingPromptTemplate,
                            user_prompt_template: e.target.value
                          })}
                          rows={6}
                          className="input-field font-mono text-sm"
                          placeholder="ユーザープロンプトテンプレートを入力（任意）..."
                        />
                      </div>
                      
                      <div className="flex justify-end space-x-2 pt-4">
                        <button
                          onClick={() => setEditingPromptTemplate(null)}
                          className="btn-secondary"
                        >
                          キャンセル
                        </button>
                        {editingPromptTemplate.id && (
                          <button
                            onClick={async () => {
                              if (confirm('このテンプレートを削除しますか？')) {
                                try {
                                  await api.delete(`/prompt-templates/${editingPromptTemplate.id}`)
                                  toast.success('テンプレートを削除しました')
                                  queryClient.invalidateQueries('prompt-templates')
                                  queryClient.invalidateQueries('technical-prompt-templates')
                                  queryClient.invalidateQueries('all-prompt-templates')
                                  setEditingPromptTemplate(null)
                                } catch (error) {
                                  toast.error('削除に失敗しました')
                                }
                              }
                            }}
                            className="btn-danger"
                          >
                            削除
                          </button>
                        )}
                        <button
                          onClick={async () => {
                            try {
                              if (editingPromptTemplate.id) {
                                // 更新
                                await api.put(`/prompt-templates/${editingPromptTemplate.id}`, {
                                  name: editingPromptTemplate.name,
                                  description: editingPromptTemplate.description,
                                  template_type: editingPromptTemplate.template_type,
                                  system_prompt: editingPromptTemplate.system_prompt,
                                  user_prompt_template: editingPromptTemplate.user_prompt_template,
                                  model_name: editingPromptTemplate.model_name,
                                  max_tokens: editingPromptTemplate.max_tokens,
                                  temperature: editingPromptTemplate.temperature
                                })
                                toast.success('テンプレートを更新しました')
                              } else {
                                // 作成
                                await api.post('/prompt-templates', {
                                  name: editingPromptTemplate.name,
                                  description: editingPromptTemplate.description,
                                  template_type: editingPromptTemplate.template_type,
                                  system_prompt: editingPromptTemplate.system_prompt,
                                  user_prompt_template: editingPromptTemplate.user_prompt_template,
                                  model_name: editingPromptTemplate.model_name,
                                  max_tokens: editingPromptTemplate.max_tokens,
                                  temperature: editingPromptTemplate.temperature
                                })
                                toast.success('テンプレートを作成しました')
                              }
                              queryClient.invalidateQueries('prompt-templates')
                              queryClient.invalidateQueries('technical-prompt-templates')
                              queryClient.invalidateQueries('all-prompt-templates')
                              setEditingPromptTemplate(null)
                              // 作成後はモーダルを閉じる
                              if (!editingPromptTemplate.id) {
                                setShowPromptEditor(false)
                              }
                            } catch (error) {
                              toast.error('保存に失敗しました')
                            }
                          }}
                          className="btn-primary"
                          disabled={!editingPromptTemplate.name || !editingPromptTemplate.system_prompt}
                        >
                          {editingPromptTemplate.id ? '更新' : '作成'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center text-gray-500 py-8">
                      左側からテンプレートを選択するか、「新規作成」ボタンを押してください
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Reports
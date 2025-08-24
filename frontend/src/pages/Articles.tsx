import React, { useState, useEffect } from 'react'
import { useQuery } from 'react-query'
import { Search, Filter, Plus, RefreshCw, Calendar, Tag, Archive } from 'lucide-react'
import toast from 'react-hot-toast'
import { articleApi } from '../services/articleApi'
import { ArticleSearchParams } from '../types'
import ArticleCard from '../components/ArticleCard'
import { useAuth } from '../contexts/AuthContext'

const Articles: React.FC = () => {
  const { isAdmin } = useAuth()
  const [searchParams, setSearchParams] = useState<ArticleSearchParams>({
    page: 1,
    limit: 100
  })
  const [searchQuery, setSearchQuery] = useState('')
  const [searchMode, setSearchMode] = useState<'and' | 'or'>('and')
  const [showFilters, setShowFilters] = useState(false)
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [dateRange, setDateRange] = useState({ start: '', end: '' })
  const [availableTags, setAvailableTags] = useState<string[]>([])
  const [selectedArticleIds, setSelectedArticleIds] = useState<string[]>([])
  const [isExporting, setIsExporting] = useState(false)

  const { data, isLoading, error, refetch } = useQuery(
    ['articles', searchParams],
    () => articleApi.getArticles(searchParams),
    {
      keepPreviousData: true,
    }
  )

  // タグ一覧を取得
  const { data: tagsData } = useQuery(
    'available-tags',
    () => articleApi.getTags(),
    {
      staleTime: 5 * 60 * 1000, // 5分間キャッシュ
    }
  )

  useEffect(() => {
    if (tagsData) {
      setAvailableTags(tagsData)
    }
  }, [tagsData])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearchParams(prev => ({
      ...prev,
      query: searchQuery.trim() || undefined,
      search_mode: searchMode,
      // 他のフィルター条件を保持
      tags: selectedTags.length > 0 ? selectedTags : undefined,
      start_date: dateRange.start || undefined,
      end_date: dateRange.end || undefined,
      page: 1
    }))
  }

  const handlePageChange = (newPage: number) => {
    setSearchParams(prev => ({ ...prev, page: newPage }))
  }

  const handleFavoriteChange = () => {
    // オプティミスティック更新
    refetch()
  }

  const handleFilterChange = (key: keyof ArticleSearchParams, value: any) => {
    setSearchParams(prev => ({
      ...prev,
      [key]: value,
      page: 1
    }))
  }

  const clearFilters = () => {
    setSearchParams({ page: 1, limit: 100 })
    setSearchQuery('')
    setSearchMode('and')
    setSelectedTags([])
    setDateRange({ start: '', end: '' })
  }

  const handleTagToggle = (tag: string) => {
    setSelectedTags(prev => {
      const newTags = prev.includes(tag) 
        ? prev.filter(t => t !== tag)
        : [...prev, tag]
      
      // 検索パラメータも更新（他の条件を保持）
      setSearchParams(prevParams => ({
        ...prevParams,
        query: searchQuery.trim() || undefined,
        search_mode: searchMode,
        tags: newTags.length > 0 ? newTags : undefined,
        start_date: dateRange.start || undefined,
        end_date: dateRange.end || undefined,
        page: 1
      }))
      
      return newTags
    })
  }

  const handleDateRangeChange = (type: 'start' | 'end', value: string) => {
    const newDateRange = { ...dateRange, [type]: value }
    setDateRange(newDateRange)
    
    // 検索パラメータも更新（他の条件を保持）
    setSearchParams(prev => ({
      ...prev,
      query: searchQuery.trim() || undefined,
      search_mode: searchMode,
      tags: selectedTags.length > 0 ? selectedTags : undefined,
      start_date: newDateRange.start || undefined,
      end_date: newDateRange.end || undefined,
      page: 1
    }))
  }



  const toggleAllArticlesSelection = () => {
    if (!data?.articles) return
    
    if (selectedArticleIds.length === data.articles.length) {
      setSelectedArticleIds([])
    } else {
      setSelectedArticleIds(data.articles.map(article => article.id.toString()))
    }
  }

  // 選択した記事のMarkdown一括エクスポート
  const exportSelectedArticlesAsMarkdown = async () => {
    if (selectedArticleIds.length === 0) {
      toast.error('エクスポートする記事を選択してください')
      return
    }

    try {
      setIsExporting(true)
      const response = await fetch('/api/articles/export/markdown/bulk', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({ article_ids: selectedArticleIds })
      })

      if (!response.ok) {
        throw new Error(`エクスポートに失敗しました (${response.status})`)
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style.display = 'none'
      a.href = url
      a.download = `selected_articles_${new Date().toISOString().split('T')[0]}.zip`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      toast.success(`${selectedArticleIds.length}件の記事をエクスポートしました`)
      setSelectedArticleIds([])
    } catch (error: any) {
      console.error('Export error:', error)
      toast.error(`エクスポートに失敗しました: ${error.message}`)
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* ヘッダー */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">記事一覧</h1>
          <p className="mt-2 text-gray-600">
            登録された記事を検索・閲覧できます
            {data && ` (${data.total}件)`}
          </p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => refetch()}
            className="btn-secondary flex items-center"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            更新
          </button>
          {isAdmin && (
            <button className="btn-primary flex items-center">
              <Plus className="w-4 h-4 mr-2" />
              記事を追加
            </button>
          )}
        </div>
      </div>

      {/* 記事選択・エクスポートコントロール */}
      {data?.articles && data.articles.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={data.articles.length > 0 && selectedArticleIds.length === data.articles.length}
                  onChange={toggleAllArticlesSelection}
                  className="form-checkbox text-primary-600"
                />
                <span className="ml-2 text-sm text-gray-700">
                  全選択 ({selectedArticleIds.length}/{data.articles.length})
                </span>
              </div>
              {selectedArticleIds.length > 0 && (
                <span className="text-sm text-primary-600">
                  {selectedArticleIds.length}件選択中
                </span>
              )}
            </div>
            
            {selectedArticleIds.length > 0 && (
              <div className="flex space-x-2">
                <button
                  onClick={exportSelectedArticlesAsMarkdown}
                  disabled={isExporting}
                  className="btn-secondary flex items-center text-sm disabled:opacity-50"
                >
                  {isExporting ? (
                    <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                  ) : (
                    <Archive className="w-4 h-4 mr-1" />
                  )}
                  Markdown一括エクスポート (ZIP)
                </button>
                <button
                  onClick={() => setSelectedArticleIds([])}
                  className="btn-secondary text-sm"
                >
                  選択をクリア
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 検索・フィルター */}
      <div className="bg-white rounded-lg shadow p-6">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex space-x-4">
            <div className="flex-1 space-y-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                <input
                  type="text"
                  placeholder="記事を検索..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="input-field pl-10"
                />
              </div>
              {/* 検索モード選択 */}
              <div className="flex items-center space-x-4 text-sm">
                <span className="text-gray-600">検索モード:</span>
                <label className="flex items-center">
                  <input
                    type="radio"
                    value="and"
                    checked={searchMode === 'and'}
                    onChange={(e) => setSearchMode(e.target.value as 'and' | 'or')}
                    className="mr-1"
                  />
                  <span>AND検索（すべて含む）</span>
                </label>
                <label className="flex items-center">
                  <input
                    type="radio"
                    value="or"
                    checked={searchMode === 'or'}
                    onChange={(e) => setSearchMode(e.target.value as 'and' | 'or')}
                    className="mr-1"
                  />
                  <span>OR検索（いずれか含む）</span>
                </label>
              </div>
            </div>
            <button type="submit" className="btn-primary">
              検索
            </button>
            <button
              type="button"
              onClick={() => setShowFilters(!showFilters)}
              className={`btn-secondary flex items-center ${showFilters ? 'bg-gray-200' : ''}`}
            >
              <Filter className="w-4 h-4 mr-2" />
              フィルター
            </button>
          </div>

          {/* フィルターパネル */}
          {showFilters && (
            <div className="border-t pt-4 space-y-4">
              {/* 第一行: ソース、日付範囲 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    ソース
                  </label>
                  <input
                    type="text"
                    placeholder="サイト名で絞り込み"
                    value={searchParams.source || ''}
                    onChange={(e) => handleFilterChange('source', e.target.value || undefined)}
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Calendar className="w-4 h-4 inline mr-1" />
                    開始日
                  </label>
                  <input
                    type="date"
                    value={dateRange.start}
                    onChange={(e) => handleDateRangeChange('start', e.target.value)}
                    className="input-field"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Calendar className="w-4 h-4 inline mr-1" />
                    終了日
                  </label>
                  <input
                    type="date"
                    value={dateRange.end}
                    onChange={(e) => handleDateRangeChange('end', e.target.value)}
                    className="input-field"
                  />
                </div>
              </div>

              {/* タグ選択 */}
              {availableTags.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Tag className="w-4 h-4 inline mr-1" />
                    タグで絞り込み
                  </label>
                  <div className="max-h-32 overflow-y-auto border rounded-md p-2 bg-gray-50">
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                      {availableTags.slice(0, 20).map((tag) => (
                        <label key={tag} className="flex items-center text-sm">
                          <input
                            type="checkbox"
                            checked={selectedTags.includes(tag)}
                            onChange={() => handleTagToggle(tag)}
                            className="rounded border-gray-300 text-primary-600 mr-2"
                          />
                          <span className="truncate" title={tag}>
                            {tag}
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                  {selectedTags.length > 0 && (
                    <div className="mt-2">
                      <p className="text-sm text-gray-600 mb-1">選択中のタグ:</p>
                      <div className="flex flex-wrap gap-1">
                        {selectedTags.map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex items-center px-2 py-1 text-xs bg-primary-100 text-primary-800 rounded-md"
                          >
                            {tag}
                            <button
                              onClick={() => handleTagToggle(tag)}
                              className="ml-1 hover:text-primary-600"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 表示設定とクリア */}
              <div className="flex items-center justify-between">
                <div>
                  <label className="flex items-center text-sm">
                    <input
                      type="checkbox"
                      checked={searchParams.favorites_only || false}
                      onChange={(e) => handleFilterChange('favorites_only', e.target.checked)}
                      className="rounded border-gray-300 text-primary-600 mr-2"
                    />
                    お気に入りのみ表示
                  </label>
                </div>
                <button
                  type="button"
                  onClick={clearFilters}
                  className="btn-secondary"
                >
                  すべてのフィルターをクリア
                </button>
              </div>
            </div>
          )}
        </form>
      </div>

      {/* 記事一覧 */}
      {isLoading ? (
        <div className="text-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-primary-600 mb-4" />
          <p className="text-gray-600">記事を読み込み中...</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-red-800">記事の読み込みに失敗しました</p>
          <button
            onClick={() => refetch()}
            className="mt-2 btn-secondary"
          >
            再試行
          </button>
        </div>
      ) : data?.articles.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-12 text-center">
          <p className="text-gray-600 text-lg">記事が見つかりません</p>
          <p className="text-gray-500 mt-2">
            {searchParams.query ? '検索条件を変更してください' : '最初の記事をスクレイピングしましょう'}
          </p>
        </div>
      ) : (
        <>
          <div className="grid gap-6">
            {data?.articles.map((article) => (
              <ArticleCard
                key={article.id}
                article={article}
                onFavoriteChange={handleFavoriteChange}
                isSelected={selectedArticleIds.includes(article.id.toString())}
                onSelectionChange={(articleId, isSelected) => {
                  if (isSelected) {
                    setSelectedArticleIds(prev => [...prev, articleId])
                  } else {
                    setSelectedArticleIds(prev => prev.filter(id => id !== articleId))
                  }
                }}
              />
            ))}
          </div>

          {/* ページネーション */}
          {data && data.total > data.limit && (
            <div className="flex items-center justify-center space-x-2">
              <button
                onClick={() => handlePageChange(data.page - 1)}
                disabled={!data.has_prev}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                前へ
              </button>
              
              <span className="px-4 py-2 text-sm text-gray-700">
                {data.page} / {Math.ceil(data.total / data.limit)}
              </span>
              
              <button
                onClick={() => handlePageChange(data.page + 1)}
                disabled={!data.has_next}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                次へ
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default Articles
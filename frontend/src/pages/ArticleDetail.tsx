import React, { useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useQuery } from 'react-query'
import { articleApi } from '../services/articleApi'
import { useAuth } from '../contexts/AuthContext'
import { 
  ArrowLeft, ExternalLink, Heart, Calendar, Clock, User, Tag, 
  Copy, Share2, BookOpen, Edit, Trash2, Save, X, Link as LinkIcon
} from 'lucide-react'
import { formatDistance } from 'date-fns'
import { ja } from 'date-fns/locale'
import toast from 'react-hot-toast'

const ArticleDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { user, isAdmin } = useAuth()
  const [isFavorite, setIsFavorite] = useState(false)
  const [isToggling, setIsToggling] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [isRegeneratingSummary, setIsRegeneratingSummary] = useState(false)
  const [editData, setEditData] = useState({
    title: '',
    summary: '',
    tags: [] as string[],
    content: ''
  })

  const { data: article, isLoading, error, refetch } = useQuery(
    ['article', id],
    () => articleApi.getArticle(id!),
    {
      enabled: !!id,
      onSuccess: (data) => {
        setIsFavorite(data.is_favorite)
        setEditData({
          title: data.title,
          summary: data.summary || '',
          tags: data.tags || [],
          content: data.content || ''
        })
      }
    }
  )

  const handleFavoriteToggle = async () => {
    if (!article) return
    
    setIsToggling(true)
    try {
      const response = await articleApi.toggleFavorite(article.id)
      setIsFavorite(response.is_favorite)
      toast.success(response.message)
    } catch (error) {
      toast.error('お気に入りの更新に失敗しました')
    } finally {
      setIsToggling(false)
    }
  }

  const handleCopyUrl = () => {
    if (article) {
      navigator.clipboard.writeText(article.url)
      toast.success('URLをコピーしました')
    }
  }

  const handleShare = async () => {
    if (!article) return
    
    const shareData = {
      title: article.title,
      text: article.summary || '記事をチェック',
      url: article.url,
    }

    if (navigator.share) {
      try {
        await navigator.share(shareData)
      } catch (error) {
        // シェアがキャンセルされた場合など
      }
    } else {
      // フォールバック: URLをコピー
      handleCopyUrl()
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return formatDistance(date, new Date(), { addSuffix: true, locale: ja })
  }

  const canEditOrDelete = () => {
    if (!article || !user) return false
    return isAdmin || article.created_by === user.id
  }

  const handleEdit = () => {
    setIsEditing(true)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    if (article) {
      setEditData({
        title: article.title,
        summary: article.summary || '',
        tags: article.tags || [],
        content: article.content || ''
      })
    }
  }

  const handleSaveEdit = async () => {
    if (!article) return

    try {
      await articleApi.updateArticle(article.id, {
        title: editData.title,
        summary: editData.summary,
        tags: editData.tags,
        content: editData.content
      })
      
      toast.success('記事を更新しました')
      setIsEditing(false)
      refetch()
    } catch (error: any) {
      console.error('記事更新エラー:', error)
      const errorMessage = error?.response?.data?.detail || error?.message || '記事の更新に失敗しました'
      toast.error(errorMessage)
    }
  }

  const handleDelete = async () => {
    if (!article) return
    
    if (!window.confirm('この記事を削除してもよろしいですか？この操作は取り消せません。')) {
      return
    }

    setIsDeleting(true)
    try {
      await articleApi.deleteArticle(article.id)
      toast.success('記事を削除しました')
      navigate('/articles')
    } catch (error) {
      toast.error('記事の削除に失敗しました')
      setIsDeleting(false)
    }
  }

  const handleTagsChange = (tagString: string) => {
    const tags = tagString.split(',').map(tag => tag.trim()).filter(tag => tag.length > 0)
    setEditData(prev => ({ ...prev, tags }))
  }

  const handleRegenerateSummary = async () => {
    if (!article) return
    
    if (!window.confirm('LLMで要約を再生成しますか？現在の要約は上書きされます。')) {
      return
    }

    setIsRegeneratingSummary(true)
    try {
      const result = await articleApi.regenerateSummary(article.id)
      toast.success(result.message)
      refetch() // 記事データを再取得して画面を更新
    } catch (error: any) {
      console.error('要約再生成エラー:', error)
      const errorMessage = error?.response?.data?.detail || error?.message || '要約の再生成に失敗しました'
      toast.error(errorMessage)
    } finally {
      setIsRegeneratingSummary(false)
    }
  }

  if (isLoading) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-4"></div>
        <p className="text-gray-600">記事を読み込み中...</p>
      </div>
    )
  }

  if (error || !article) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <p className="text-red-800 mb-4">記事の読み込みに失敗しました</p>
        <div className="space-x-2">
          <button onClick={() => refetch()} className="btn-secondary">
            再試行
          </button>
          <button onClick={() => navigate('/articles')} className="btn-primary">
            記事一覧に戻る
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* ナビゲーション */}
      <div className="mb-6">
        <button
          onClick={() => {
            // URLクエリパラメータから記事一覧の状態を復元
            const searchParams = new URLSearchParams(location.search)
            const returnPath = searchParams.get('returnPath') || '/articles'
            navigate(returnPath)
          }}
          className="flex items-center text-gray-600 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          記事一覧に戻る
        </button>
      </div>

      {/* 記事ヘッダー */}
      <div className="bg-white rounded-lg shadow-sm border mb-6">
        <div className="p-6">
          {/* タイトルとアクション */}
          <div className="flex justify-between items-start mb-4">
            {isEditing ? (
              <input
                type="text"
                value={editData.title}
                onChange={(e) => setEditData(prev => ({ ...prev, title: e.target.value }))}
                className="text-3xl font-bold text-gray-900 leading-tight bg-transparent border-b-2 border-blue-500 flex-1 mr-4 focus:outline-none"
                placeholder="記事タイトル"
              />
            ) : (
              <h1 className="text-3xl font-bold text-gray-900 leading-tight">
                {article.title}
              </h1>
            )}
            <div className="flex items-center space-x-2 ml-4">
              <button
                onClick={handleFavoriteToggle}
                disabled={isToggling}
                className={`p-2 rounded-full transition-colors ${
                  isFavorite 
                    ? 'text-red-500 hover:text-red-600' 
                    : 'text-gray-400 hover:text-red-500'
                }`}
                title={isFavorite ? 'お気に入りから削除' : 'お気に入りに追加'}
              >
                <Heart className={`w-5 h-5 ${isFavorite ? 'fill-current' : ''}`} />
              </button>
              
              <button
                onClick={handleCopyUrl}
                className="p-2 text-gray-400 hover:text-gray-600 rounded-full transition-colors"
                title="URLをコピー"
              >
                <Copy className="w-5 h-5" />
              </button>
              
              <button
                onClick={handleShare}
                className="p-2 text-gray-400 hover:text-gray-600 rounded-full transition-colors"
                title="共有"
              >
                <Share2 className="w-5 h-5" />
              </button>

              {canEditOrDelete() && (
                <div className="flex space-x-1 border-l pl-2 ml-2">
                  {isEditing ? (
                    <>
                      <button
                        onClick={handleSaveEdit}
                        className="p-2 text-gray-400 hover:text-green-600 rounded-full transition-colors"
                        title="保存"
                      >
                        <Save className="w-4 h-4" />
                      </button>
                      <button
                        onClick={handleCancelEdit}
                        className="p-2 text-gray-400 hover:text-gray-600 rounded-full transition-colors"
                        title="キャンセル"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={handleEdit}
                        className="p-2 text-gray-400 hover:text-blue-600 rounded-full transition-colors"
                        title="編集"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={handleDelete}
                        disabled={isDeleting}
                        className="p-2 text-gray-400 hover:text-red-600 rounded-full transition-colors disabled:opacity-50"
                        title="削除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* メタ情報 */}
          <div className="space-y-3 text-sm text-gray-600 mb-6">
            {/* URL表示 */}
            <div className="flex items-center justify-between bg-gray-50 rounded-lg p-3">
              <div className="flex items-center flex-1 min-w-0">
                <LinkIcon className="w-4 h-4 mr-2 text-gray-500 flex-shrink-0" />
                <span className="text-xs text-gray-500 mr-2">URL:</span>
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-800 hover:underline truncate flex-1"
                  title={article.url}
                >
                  {article.url}
                </a>
              </div>
              <button
                onClick={handleCopyUrl}
                className="ml-2 p-1 text-gray-400 hover:text-gray-600 rounded transition-colors flex-shrink-0"
                title="URLをコピー"
              >
                <Copy className="w-4 h-4" />
              </button>
            </div>

            {/* その他のメタ情報 */}
            <div className="flex flex-wrap items-center gap-6">
              {article.source && (
                <span className="flex items-center">
                  <ExternalLink className="w-4 h-4 mr-1" />
                  {article.source}
                </span>
              )}
              
              <span className="flex items-center">
                <Clock className="w-4 h-4 mr-1" />
                {formatDate(article.scraped_date)}
              </span>

              {article.published_date && (
                <span className="flex items-center">
                  <Calendar className="w-4 h-4 mr-1" />
                  公開: {formatDate(article.published_date)}
                </span>
              )}
            </div>
          </div>

          {/* タグ */}
          <div className="mb-6">
            {isEditing ? (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  タグ（カンマ区切り）
                </label>
                <input
                  type="text"
                  value={editData.tags.join(', ')}
                  onChange={(e) => handleTagsChange(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="タグをカンマ区切りで入力"
                />
              </div>
            ) : (
              article.tags && article.tags.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {article.tags.map((tag, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center px-3 py-1 text-sm font-medium bg-primary-100 text-primary-800 rounded-full"
                    >
                      <Tag className="w-3 h-3 mr-1" />
                      {tag}
                    </span>
                  ))}
                </div>
              )
            )}
          </div>

          {/* 要約 */}
          <div className="bg-primary-50 border-l-4 border-primary-400 p-4 mb-6">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-primary-900 flex items-center">
                <BookOpen className="w-4 h-4 mr-2" />
                要約
              </h2>
              {/* 要約再生成ボタン（管理者のみ、編集中以外） */}
              {isAdmin && !isEditing && (
                <button
                  onClick={handleRegenerateSummary}
                  disabled={isRegeneratingSummary}
                  className="text-xs px-3 py-1 bg-primary-600 text-white rounded hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  title="LLMで要約を再生成"
                >
                  {isRegeneratingSummary ? '生成中...' : 'AI要約生成'}
                </button>
              )}
            </div>
            {isEditing ? (
              <textarea
                value={editData.summary}
                onChange={(e) => setEditData(prev => ({ ...prev, summary: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
                rows={4}
                placeholder="記事の要約を入力"
              />
            ) : (
              <p className="text-primary-800 leading-relaxed">
                {article.summary || '要約が設定されていません'}
              </p>
            )}
          </div>

          {/* 元記事リンク */}
          <div className="border-t pt-4">
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
            >
              <ExternalLink className="w-4 h-4 mr-2" />
              元記事を読む
            </a>
          </div>
        </div>
      </div>

      {/* 記事本文 */}
      <div className="bg-white rounded-lg shadow-sm border">
        <div className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">記事内容</h2>
          {isEditing ? (
            <textarea
              value={editData.content}
              onChange={(e) => setEditData(prev => ({ ...prev, content: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              rows={15}
              placeholder="記事の内容を入力"
            />
          ) : (
            <div className="prose max-w-none">
              <div 
                className="text-gray-700 leading-relaxed whitespace-pre-wrap"
                style={{ wordBreak: 'break-word' }}
              >
                {article.content || '記事内容が設定されていません'}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 関連情報 */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">記事情報</h3>
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="font-medium text-gray-700">記事ID</dt>
              <dd className="text-gray-600 font-mono text-xs">{article.id}</dd>
            </div>
            <div>
              <dt className="font-medium text-gray-700">取得日時</dt>
              <dd className="text-gray-600">
                {new Date(article.scraped_date).toLocaleString('ja-JP')}
              </dd>
            </div>
            {article.created_by && (
              <div>
                <dt className="font-medium text-gray-700">登録者</dt>
                <dd className="text-gray-600 flex items-center">
                  <User className="w-3 h-3 mr-1" />
                  {article.created_by}
                </dd>
              </div>
            )}
          </dl>
        </div>

        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">アクション</h3>
          <div className="space-y-3">
            <button
              onClick={() => {
                const searchParams = new URLSearchParams(location.search)
                const returnPath = searchParams.get('returnPath') || '/articles'
                navigate(returnPath)
              }}
              className="block w-full text-center btn-secondary"
            >
              記事一覧に戻る
            </button>
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full text-center btn-primary"
            >
              元記事を新しいタブで開く
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ArticleDetail
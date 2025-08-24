import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Article } from '../types'
import { Heart, ExternalLink, Clock, Tag, Calendar } from 'lucide-react'
import { articleApi } from '../services/articleApi'
import toast from 'react-hot-toast'
import { formatDistance } from 'date-fns'
import { ja } from 'date-fns/locale'

interface ArticleCardProps {
  article: Article
  onFavoriteChange?: (articleId: string, isFavorite: boolean) => void
  isSelected?: boolean
  onSelectionChange?: (articleId: string, isSelected: boolean) => void
}

const ArticleCard: React.FC<ArticleCardProps> = ({ article, onFavoriteChange, isSelected = false, onSelectionChange }) => {
  const [isFavorite, setIsFavorite] = useState(article.is_favorite)
  const [isToggling, setIsToggling] = useState(false)
  const location = useLocation()

  const handleFavoriteToggle = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()

    setIsToggling(true)
    try {
      const response = await articleApi.toggleFavorite(article.id)
      setIsFavorite(response.is_favorite)
      onFavoriteChange?.(article.id, response.is_favorite)
      toast.success(response.message)
    } catch (error) {
      toast.error('お気に入りの更新に失敗しました')
    } finally {
      setIsToggling(false)
    }
  }

  const handleSelectionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation()
    onSelectionChange?.(article.id, e.target.checked)
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return formatDistance(date, new Date(), { addSuffix: true, locale: ja })
  }

  return (
    <div className={`bg-white rounded-lg shadow hover:shadow-md transition-shadow border ${isSelected ? 'ring-2 ring-primary-500' : ''}`}>
      <div className="p-6">
        {/* ヘッダー */}
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-start space-x-3 flex-1">
            {onSelectionChange && (
              <input
                type="checkbox"
                checked={isSelected}
                onChange={handleSelectionChange}
                className="form-checkbox text-primary-600 mt-1"
              />
            )}
            <h3 className="text-lg font-semibold text-gray-900 line-clamp-2 leading-snug flex-1">
              <Link 
                to={`/articles/${article.id}?returnPath=${encodeURIComponent(location.pathname + location.search)}`}
                className="hover:text-primary-600 transition-colors"
              >
                {article.title}
              </Link>
            </h3>
          </div>
          <button
            onClick={handleFavoriteToggle}
            disabled={isToggling}
            className={`ml-3 p-1 rounded-full transition-colors ${
              isFavorite 
                ? 'text-red-500 hover:text-red-600' 
                : 'text-gray-400 hover:text-red-500'
            }`}
          >
            <Heart 
              className={`w-5 h-5 ${isFavorite ? 'fill-current' : ''}`} 
            />
          </button>
        </div>

        {/* 要約 */}
        {article.summary && (
          <p className="text-gray-600 text-sm mb-4 line-clamp-3">
            {article.summary}
          </p>
        )}

        {/* タグ */}
        {article.tags && article.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {article.tags.slice(0, 3).map((tag, index) => (
              <span
                key={index}
                className="inline-flex items-center px-2 py-1 text-xs font-medium bg-primary-100 text-primary-800 rounded-full"
              >
                <Tag className="w-3 h-3 mr-1" />
                {tag}
              </span>
            ))}
            {article.tags.length > 3 && (
              <span className="text-xs text-gray-500">
                +{article.tags.length - 3} more
              </span>
            )}
          </div>
        )}

        {/* メタ情報 */}
        <div className="flex items-center justify-between text-sm text-gray-500">
          <div className="flex items-center space-x-4">
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
          </div>
          
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-3 py-1 text-xs font-medium text-primary-700 bg-primary-50 rounded-full hover:bg-primary-100 transition-colors"
          >
            <ExternalLink className="w-3 h-3 mr-1" />
            元記事を開く
          </a>
        </div>

        {/* 公開日 */}
        {article.published_date && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <span className="flex items-center text-sm text-gray-500">
              <Calendar className="w-4 h-4 mr-1" />
              公開日: {formatDate(article.published_date)}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default ArticleCard
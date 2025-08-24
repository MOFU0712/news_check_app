import React from 'react'
import { useQuery } from 'react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { articleApi } from '../services/articleApi'
import api from '../services/api'
import { FileText, Upload, Download, Search, Users, Heart, Calendar } from 'lucide-react'

const Dashboard: React.FC = () => {
  const { user, isAdmin } = useAuth()
  
  const { data: statsData, isLoading: statsLoading } = useQuery(
    'article-stats',
    articleApi.getStats,
    {
      refetchInterval: 5 * 60 * 1000, // 5分ごとに更新
    }
  )

  // お気に入り記事を取得（5件まで）
  const { data: favoriteArticles, isLoading: favoritesLoading } = useQuery(
    'dashboard-favorite-articles',
    () => articleApi.getArticles({ favorites_only: true, limit: 5 }),
    {
      staleTime: 2 * 60 * 1000, // 2分間キャッシュ
    }
  )

  // 最新レポートを取得（5件まで）
  const { data: recentReports, isLoading: reportsLoading } = useQuery(
    'dashboard-recent-reports',
    async () => {
      const response = await api.get('/reports/saved?limit=5')
      return response.data
    },
    {
      staleTime: 2 * 60 * 1000, // 2分間キャッシュ
    }
  )

  const stats = [
    { 
      name: '登録記事数', 
      value: statsLoading ? '...' : (statsData?.total_articles?.toString() || '0'), 
      icon: FileText, 
      color: 'bg-blue-500',
      href: '/articles'
    },
    { 
      name: '今月の記事', 
      value: statsLoading ? '...' : (statsData?.monthly_articles?.toString() || '0'), 
      icon: Upload, 
      color: 'bg-green-500',
      href: '/articles'
    },
    { name: 'エクスポート回数', value: '0', icon: Download, color: 'bg-purple-500' },
    { name: '検索回数', value: '0', icon: Search, color: 'bg-orange-500' },
  ]

  if (isAdmin) {
    stats.push({ name: '登録ユーザー数', value: '1', icon: Users, color: 'bg-red-500' })
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">ダッシュボード</h1>
        <p className="mt-2 text-gray-600">
          おかえりなさい、{user?.email}さん
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {stats.map((stat) => {
          const Icon = stat.icon
          const StatCard = (
            <div key={stat.name} className="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow">
              <div className="flex items-center">
                <div className={`${stat.color} rounded-lg p-3`}>
                  <Icon className="w-6 h-6 text-white" />
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">{stat.name}</p>
                  <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
                </div>
              </div>
            </div>
          )
          
          return stat.href ? (
            <Link key={stat.name} to={stat.href}>
              {StatCard}
            </Link>
          ) : StatCard
        })}
      </div>

      {/* お気に入り記事と最新レポート */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* お気に入り記事 */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium text-gray-900 flex items-center">
                <FileText className="w-5 h-5 mr-2" />
                お気に入り記事
              </h2>
              <Link 
                to="/articles?favorites=true"
                className="text-sm text-primary-600 hover:text-primary-800"
              >
                すべて見る
              </Link>
            </div>
          </div>
          <div className="p-6">
            {favoritesLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="animate-pulse flex space-x-3">
                    <div className="w-3 h-3 bg-gray-300 rounded-full mt-1.5"></div>
                    <div className="flex-1">
                      <div className="h-4 bg-gray-300 rounded w-3/4 mb-2"></div>
                      <div className="h-3 bg-gray-300 rounded w-1/2"></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : favoriteArticles && favoriteArticles.articles.length > 0 ? (
              <div className="space-y-3">
                {favoriteArticles.articles.slice(0, 5).map((article) => (
                  <div key={article.id} className="group">
                    <Link 
                      to={`/articles/${article.id}`}
                      className="flex items-start space-x-3 p-3 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <Heart className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0 fill-current" />
                      <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-medium text-gray-900 line-clamp-2 group-hover:text-primary-600">
                          {article.title}
                        </h3>
                        <div className="flex items-center space-x-2 mt-1 text-xs text-gray-500">
                          <Calendar className="w-3 h-3" />
                          <span>{new Date(article.created_at).toLocaleDateString('ja-JP')}</span>
                          {article.tags && article.tags.length > 0 && (
                            <>
                              <span>•</span>
                              <span className="truncate">{article.tags.join(', ')}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </Link>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Heart className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="text-sm text-gray-500">お気に入り記事がありません</p>
                <Link 
                  to="/articles"
                  className="text-sm text-primary-600 hover:text-primary-800 mt-2 inline-block"
                >
                  記事を探す
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* 最新のレポート */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium text-gray-900 flex items-center">
                <FileText className="w-5 h-5 mr-2" />
                最新のレポート
              </h2>
              <Link 
                to="/reports"
                className="text-sm text-primary-600 hover:text-primary-800"
              >
                すべて見る
              </Link>
            </div>
          </div>
          <div className="p-6">
            {reportsLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="animate-pulse flex space-x-3">
                    <div className="w-3 h-3 bg-gray-300 rounded-full mt-1.5"></div>
                    <div className="flex-1">
                      <div className="h-4 bg-gray-300 rounded w-3/4 mb-2"></div>
                      <div className="h-3 bg-gray-300 rounded w-1/2"></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : recentReports && recentReports.length > 0 ? (
              <div className="space-y-3">
                {recentReports.slice(0, 5).map((report: any) => (
                  <div key={report.id} className="group">
                    <Link 
                      to={`/reports`}
                      className="flex items-start space-x-3 p-3 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <FileText className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-medium text-gray-900 line-clamp-2 group-hover:text-primary-600">
                          {report.title}
                        </h3>
                        <div className="flex items-center space-x-2 mt-1 text-xs text-gray-500">
                          <Calendar className="w-3 h-3" />
                          <span>{new Date(report.created_at).toLocaleDateString('ja-JP')}</span>
                          <span>•</span>
                          <span className="capitalize">
                            {report.report_type === 'summary' && '概要レポート'}
                            {report.report_type === 'tag_analysis' && 'タグ分析'}
                            {report.report_type === 'source_analysis' && 'ソース分析'}
                            {report.report_type === 'trend_analysis' && 'トレンド分析'}
                            {report.report_type === 'technical_summary' && '技術まとめ'}
                            {!['summary', 'tag_analysis', 'source_analysis', 'trend_analysis', 'technical_summary'].includes(report.report_type) && report.report_type}
                          </span>
                        </div>
                        {report.summary && (
                          <p className="text-xs text-gray-600 mt-1 line-clamp-2">
                            {report.summary}
                          </p>
                        )}
                      </div>
                    </Link>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <FileText className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="text-sm text-gray-500">レポートがありません</p>
                <Link 
                  to="/reports"
                  className="text-sm text-primary-600 hover:text-primary-800 mt-2 inline-block"
                >
                  レポートを作成
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
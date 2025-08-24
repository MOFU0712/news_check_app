import api from './api'
import { Article, ArticleCreate, ArticleUpdate, ArticleListResponse, ArticleSearchParams } from '../types'

export const articleApi = {
  // 記事一覧取得
  getArticles: async (params: ArticleSearchParams = {}): Promise<ArticleListResponse> => {
    const searchParams = new URLSearchParams()
    
    if (params.query) searchParams.append('query', params.query)
    if (params.search_mode) searchParams.append('search_mode', params.search_mode)
    if (params.tags && params.tags.length > 0) {
      params.tags.forEach(tag => searchParams.append('tags', tag))
    }
    if (params.source) searchParams.append('source', params.source)
    if (params.start_date) searchParams.append('start_date', params.start_date)
    if (params.end_date) searchParams.append('end_date', params.end_date)
    if (params.favorites_only) searchParams.append('favorites_only', 'true')
    if (params.page) searchParams.append('page', params.page.toString())
    if (params.limit) searchParams.append('limit', params.limit.toString())
    
    const response = await api.get<ArticleListResponse>(`/articles?${searchParams}`)
    return response.data
  },

  // 記事詳細取得
  getArticle: async (id: string): Promise<Article> => {
    const response = await api.get<Article>(`/articles/${id}`)
    return response.data
  },

  // 記事作成
  createArticle: async (data: ArticleCreate): Promise<Article> => {
    const response = await api.post<Article>('/articles', data)
    return response.data
  },

  // 記事更新（管理者のみ）
  updateArticle: async (id: string, data: ArticleUpdate): Promise<Article> => {
    const response = await api.put<Article>(`/articles/${id}`, data)
    return response.data
  },

  // 記事削除（管理者のみ）
  deleteArticle: async (id: string): Promise<void> => {
    await api.delete(`/articles/${id}`)
  },

  // お気に入り切り替え
  toggleFavorite: async (articleId: string): Promise<{ article_id: string; is_favorite: boolean; message: string }> => {
    const response = await api.post('/articles/favorites', { article_id: articleId })
    return response.data
  },

  // 記事統計取得
  getStats: async (): Promise<{
    total_articles: number
    monthly_articles: number
    popular_tags: Array<[string, number]>
    source_stats: Array<[string, number]>
  }> => {
    const response = await api.get('/articles/stats/overview')
    return response.data
  },

  // 利用可能なタグ一覧取得
  getTags: async (): Promise<string[]> => {
    const response = await api.get<{tags: string[]}>('/articles/tags')
    return response.data.tags
  },

  // 要約を再生成（管理者のみ）
  regenerateSummary: async (id: string): Promise<{ message: string; summary: string }> => {
    const response = await api.post(`/llm/articles/${id}/generate-summary`)
    return { 
      message: 'LLM要約を生成しました',
      summary: response.data.summary 
    }
  }
}
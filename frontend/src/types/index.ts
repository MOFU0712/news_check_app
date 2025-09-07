export interface User {
  id: string
  email: string
  is_admin: boolean
  is_active: boolean
  password_change_required: boolean
}

export interface LoginData {
  email: string
  password: string
}

export interface RegisterData {
  email: string
  password: string
  token: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
}

export interface Article {
  id: string
  title: string
  url: string
  content?: string
  source?: string
  published_date?: string
  scraped_date: string
  tags?: string[]
  summary?: string
  created_by?: string
  created_at: string
  updated_at: string
  is_favorite: boolean
}

export interface ArticleCreate {
  title: string
  url: string
  content?: string
  source?: string
  published_date?: string
  tags?: string[]
  summary?: string
}

export interface ArticleUpdate {
  title?: string
  url?: string
  content?: string
  source?: string
  published_date?: string
  tags?: string[]
  summary?: string
}

export interface ArticleListResponse {
  articles: Article[]
  total: number
  page: number
  limit: number
  has_next: boolean
  has_prev: boolean
}

export interface ArticleSearchParams {
  query?: string
  search_mode?: 'and' | 'or'
  tags?: string[]
  source?: string
  favorites_only?: boolean
  start_date?: string
  end_date?: string
  page?: number
  limit?: number
}
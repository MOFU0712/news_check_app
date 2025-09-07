import api from './api'

export interface UsageInfo {
  can_use: boolean
  remaining_count: number
  daily_limit: number
  used_count: number
  reset_time: string
  message: string
}

export interface UsageSummary {
  user_id: string
  is_admin: boolean
  usage_date: string
  actions: {
    [actionType: string]: UsageInfo
  }
}

export interface UsageLog {
  id: string
  action_type: string
  usage_date: string
  resource_used: string
  created_at: string
}

export interface UsageHistory {
  user_id: string
  period_days: number
  total_logs: number
  logs: UsageLog[]
}

export const usageApi = {
  // 使用状況サマリーを取得
  getUsageStatus: async (): Promise<UsageSummary> => {
    const response = await api.get<UsageSummary>('/usage/status')
    return response.data
  },

  // 特定のアクションタイプの使用状況を取得
  getActionUsageStatus: async (actionType: string): Promise<UsageInfo> => {
    const response = await api.get<UsageInfo>(`/usage/status/${actionType}`)
    return response.data
  },

  // 使用履歴を取得
  getUsageHistory: async (days: number = 7): Promise<UsageHistory> => {
    const response = await api.get<UsageHistory>(`/usage/history?days=${days}`)
    return response.data
  }
}

export default usageApi
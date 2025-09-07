import React from 'react'
import { useQuery } from 'react-query'
import { AlertCircle, CheckCircle, Clock } from 'lucide-react'
import { usageApi, UsageInfo } from '../services/usageApi'

interface UsageIndicatorProps {
  actionType: string
  className?: string
}

const UsageIndicator: React.FC<UsageIndicatorProps> = ({ actionType, className = '' }) => {
  const { data: usageInfo, isLoading } = useQuery(
    ['usage-status', actionType],
    () => usageApi.getActionUsageStatus(actionType),
    {
      refetchInterval: 60000, // 1分ごとに更新
      retry: false
    }
  )

  if (isLoading || !usageInfo) {
    return (
      <div className={`flex items-center space-x-2 text-gray-500 ${className}`}>
        <Clock className="h-4 w-4 animate-spin" />
        <span className="text-sm">使用状況を取得中...</span>
      </div>
    )
  }

  // 管理者の場合
  if (usageInfo.daily_limit === -1) {
    return (
      <div className={`flex items-center space-x-2 text-green-600 ${className}`}>
        <CheckCircle className="h-4 w-4" />
        <span className="text-sm font-medium">無制限</span>
      </div>
    )
  }

  // 制限なしの場合
  if (usageInfo.daily_limit === 0) {
    return (
      <div className={`flex items-center space-x-2 text-green-600 ${className}`}>
        <CheckCircle className="h-4 w-4" />
        <span className="text-sm">{usageInfo.message}</span>
      </div>
    )
  }

  // 使用可能な場合
  if (usageInfo.can_use) {
    const isLowRemaining = usageInfo.remaining_count <= 1
    return (
      <div className={`flex items-center space-x-2 ${isLowRemaining ? 'text-orange-600' : 'text-green-600'} ${className}`}>
        <CheckCircle className="h-4 w-4" />
        <span className="text-sm">
          残り <span className="font-medium">{usageInfo.remaining_count}</span> / {usageInfo.daily_limit} 回
        </span>
      </div>
    )
  }

  // 制限に達している場合
  return (
    <div className={`flex items-center space-x-2 text-red-600 ${className}`}>
      <AlertCircle className="h-4 w-4" />
      <div className="text-sm">
        <div className="font-medium">本日の使用制限に達しました</div>
        <div className="text-xs text-gray-500">リセット: {usageInfo.reset_time}</div>
      </div>
    </div>
  )
}

export default UsageIndicator
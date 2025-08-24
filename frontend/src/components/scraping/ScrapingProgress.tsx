import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  StopCircle,
  RefreshCw,
  ExternalLink,
  TrendingUp,
  AlertTriangle
} from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/hooks/useAuth';

interface ScrapingJob {
  job_id: string;
  parsed_urls: string[];
  duplicate_urls: string[];
  invalid_urls: Array<{ url: string; reason: string }>;
  estimated_time: string;
}

interface JobStatus {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  total: number;
  completed_urls: string[];
  failed_urls: Array<{ url: string; error: string }>;
  created_articles: string[];
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

interface ScrapingProgressProps {
  job: ScrapingJob;
  onJobComplete: () => void;
  onJobCancel: (jobId: string) => Promise<boolean>;
}

export const ScrapingProgress: React.FC<ScrapingProgressProps> = ({
  job,
  onJobComplete,
  onJobCancel
}) => {
  const { token } = useAuth();
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // 進捗取得
  const fetchJobStatus = useCallback(async () => {
    try {
      const response = await fetch(`/api/scrape/jobs/${job.job_id}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const status: JobStatus = await response.json();
      setJobStatus(status);
      setLastUpdate(new Date());

      // 完了時の処理
      if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
        setTimeout(onJobComplete, 2000); // 2秒後にコールバック実行
      }
    } catch (err) {
      console.error('Failed to fetch job status:', err);
      toast.error('進捗の取得に失敗しました');
    }
  }, [job.job_id, token, onJobComplete]);

  // キャンセル処理
  const handleCancel = useCallback(async () => {
    setIsLoading(true);
    const success = await onJobCancel(job.job_id);
    setIsLoading(false);
    if (success) {
      // キャンセル後に状態を更新
      setTimeout(fetchJobStatus, 500);
    }
  }, [job.job_id, onJobCancel, fetchJobStatus]);

  // 定期的な進捗更新
  useEffect(() => {
    fetchJobStatus(); // 初回取得

    const interval = setInterval(() => {
      if (jobStatus?.status === 'pending' || jobStatus?.status === 'running') {
        fetchJobStatus();
      }
    }, 2000); // 2秒間隔

    return () => clearInterval(interval);
  }, [fetchJobStatus, jobStatus?.status]);

  // ステータスに応じた表示
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return <Badge variant="outline" className="text-blue-600">待機中</Badge>;
      case 'running':
        return <Badge variant="outline" className="text-yellow-600">実行中</Badge>;
      case 'completed':
        return <Badge variant="outline" className="text-green-600">完了</Badge>;
      case 'failed':
        return <Badge variant="destructive">失敗</Badge>;
      case 'cancelled':
        return <Badge variant="secondary">キャンセル</Badge>;
      default:
        return <Badge variant="outline">不明</Badge>;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="h-4 w-4 text-blue-600" />;
      case 'running':
        return <Loader2 className="h-4 w-4 text-yellow-600 animate-spin" />;
      case 'completed':
        return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-600" />;
      case 'cancelled':
        return <StopCircle className="h-4 w-4 text-gray-600" />;
      default:
        return <AlertTriangle className="h-4 w-4" />;
    }
  };

  const progressPercentage = jobStatus ? (jobStatus.progress / jobStatus.total) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* 進捗サマリーカード */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              {jobStatus && getStatusIcon(jobStatus.status)}
              スクレイピング進捗
            </span>
            <div className="flex items-center gap-2">
              {jobStatus && getStatusBadge(jobStatus.status)}
              <Button
                variant="outline"
                size="sm"
                onClick={fetchJobStatus}
                disabled={isLoading}
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 基本情報 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">
                {jobStatus?.progress || 0} / {jobStatus?.total || job.parsed_urls.length}
              </div>
              <div className="text-sm text-muted-foreground">処理済み</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {jobStatus?.completed_urls.length || 0}
              </div>
              <div className="text-sm text-muted-foreground">成功</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {jobStatus?.failed_urls.length || 0}
              </div>
              <div className="text-sm text-muted-foreground">失敗</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {jobStatus?.created_articles.length || 0}
              </div>
              <div className="text-sm text-muted-foreground">記事作成</div>
            </div>
          </div>

          {/* 進捗バー */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">
                進捗: {progressPercentage.toFixed(1)}%
              </span>
              <span className="text-sm text-muted-foreground">
                推定時間: {job.estimated_time}
              </span>
            </div>
            <Progress value={progressPercentage} className="w-full" />
          </div>

          {/* アクションボタン */}
          {jobStatus && (jobStatus.status === 'pending' || jobStatus.status === 'running') && (
            <div className="flex justify-center">
              <Button
                variant="outline"
                onClick={handleCancel}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <StopCircle className="h-4 w-4 mr-2" />
                )}
                キャンセル
              </Button>
            </div>
          )}

          {/* 最終更新時刻 */}
          <div className="text-center text-sm text-muted-foreground">
            最終更新: {lastUpdate.toLocaleTimeString()}
          </div>
        </CardContent>
      </Card>

      {/* 詳細結果カード */}
      {jobStatus && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              処理詳細
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* 成功したURL */}
            {jobStatus.completed_urls.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium text-green-600 flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4" />
                  処理成功 ({jobStatus.completed_urls.length}件)
                </h4>
                <ScrollArea className="h-32 w-full border rounded p-2">
                  <div className="space-y-1">
                    {jobStatus.completed_urls.map((url, index) => (
                      <div key={index} className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs text-green-600">
                          ✓
                        </Badge>
                        <code className="text-xs flex-1">{url}</code>
                        <Button variant="ghost" size="sm" asChild>
                          <a href={url} target="_blank" rel="noopener noreferrer">
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        </Button>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}

            {/* 失敗したURL */}
            {jobStatus.failed_urls.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium text-red-600 flex items-center gap-2">
                  <XCircle className="h-4 w-4" />
                  処理失敗 ({jobStatus.failed_urls.length}件)
                </h4>
                <ScrollArea className="h-32 w-full border rounded p-2">
                  <div className="space-y-2">
                    {jobStatus.failed_urls.map((item, index) => (
                      <div key={index} className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs text-red-600">
                            ✗
                          </Badge>
                          <code className="text-xs flex-1">{item.url}</code>
                        </div>
                        <p className="text-xs text-red-600 ml-6">{item.error}</p>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            )}

            <Separator />

            {/* 作成された記事 */}
            {jobStatus.created_articles.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium text-blue-600 flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4" />
                  作成された記事 ({jobStatus.created_articles.length}件)
                </h4>
                <div className="flex flex-wrap gap-2">
                  {jobStatus.created_articles.slice(0, 10).map((articleId, index) => (
                    <Badge key={index} variant="secondary">
                      記事 #{articleId.slice(-8)}
                    </Badge>
                  ))}
                  {jobStatus.created_articles.length > 10 && (
                    <Badge variant="outline">
                      +{jobStatus.created_articles.length - 10} 件
                    </Badge>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 完了時のメッセージ */}
      {jobStatus?.status === 'completed' && (
        <Alert className="border-green-200 bg-green-50">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            スクレイピングが正常に完了しました！
            {jobStatus.created_articles.length > 0 && 
              ` ${jobStatus.created_articles.length}件の記事が作成されました。`
            }
          </AlertDescription>
        </Alert>
      )}

      {jobStatus?.status === 'failed' && (
        <Alert variant="destructive">
          <XCircle className="h-4 w-4" />
          <AlertDescription>
            スクレイピング処理でエラーが発生しました。詳細は管理者にお問い合わせください。
          </AlertDescription>
        </Alert>
      )}

      {jobStatus?.status === 'cancelled' && (
        <Alert>
          <StopCircle className="h-4 w-4" />
          <AlertDescription>
            スクレイピング処理がキャンセルされました。
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
};
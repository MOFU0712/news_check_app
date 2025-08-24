import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  CheckCircle2,
  XCircle,
  Clock,
  StopCircle,
  MoreHorizontal,
  Trash2,
  Eye,
  RefreshCw,
  Calendar,
  TrendingUp,
  AlertTriangle
} from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/hooks/useAuth';

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

export const ScrapingHistory: React.FC = () => {
  const { token } = useAuth();
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [selectedJob, setSelectedJob] = useState<JobStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // ジョブ一覧取得
  const fetchJobs = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/scrape/jobs', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setJobs(data || []);
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
      toast.error('ジョブ履歴の取得に失敗しました');
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  // ジョブ削除
  const deleteJob = useCallback(async (jobId: string) => {
    try {
      const response = await fetch(`/api/scrape/jobs/${jobId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      toast.success('ジョブを削除しました');
      fetchJobs(); // 一覧を再取得
    } catch (err) {
      console.error('Failed to delete job:', err);
      toast.error('ジョブの削除に失敗しました');
    }
  }, [token, fetchJobs]);

  // ジョブ詳細表示
  const showJobDetails = useCallback((job: JobStatus) => {
    setSelectedJob(job);
    setIsDialogOpen(true);
  }, []);

  // 初回ロード
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // ステータス表示
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
        return <Clock className="h-4 w-4 text-yellow-600 animate-pulse" />;
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

  // 統計計算
  const stats = {
    total: jobs.length,
    completed: jobs.filter(j => j.status === 'completed').length,
    running: jobs.filter(j => j.status === 'running').length,
    failed: jobs.filter(j => j.status === 'failed').length,
    totalArticles: jobs.reduce((sum, job) => sum + (job.created_articles?.length || 0), 0)
  };

  return (
    <div className="space-y-6">
      {/* 統計サマリー */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              スクレイピング統計
            </span>
            <Button variant="outline" size="sm" onClick={fetchJobs} disabled={isLoading}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold">{stats.total}</div>
              <div className="text-sm text-muted-foreground">総ジョブ数</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{stats.completed}</div>
              <div className="text-sm text-muted-foreground">完了</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600">{stats.running}</div>
              <div className="text-sm text-muted-foreground">実行中</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">{stats.failed}</div>
              <div className="text-sm text-muted-foreground">失敗</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{stats.totalArticles}</div>
              <div className="text-sm text-muted-foreground">作成記事数</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ジョブ履歴テーブル */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            ジョブ履歴
          </CardTitle>
        </CardHeader>
        <CardContent>
          {jobs.length === 0 ? (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                スクレイピングジョブの履歴がありません。
              </AlertDescription>
            </Alert>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ステータス</TableHead>
                  <TableHead>進捗</TableHead>
                  <TableHead>作成記事数</TableHead>
                  <TableHead>作成日時</TableHead>
                  <TableHead>完了日時</TableHead>
                  <TableHead className="w-[50px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(job.status)}
                        {getStatusBadge(job.status)}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <div className="text-sm">
                          {job.progress} / {job.total}
                        </div>
                        <div className="w-20 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full"
                            style={{
                              width: `${job.total > 0 ? (job.progress / job.total) * 100 : 0}%`
                            }}
                          />
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">
                        {job.created_articles?.length || 0}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {new Date(job.created_at).toLocaleString()}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {job.completed_at 
                          ? new Date(job.completed_at).toLocaleString()
                          : '-'
                        }
                      </div>
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => showJobDetails(job)}>
                            <Eye className="h-4 w-4 mr-2" />
                            詳細を表示
                          </DropdownMenuItem>
                          {(job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') && (
                            <DropdownMenuItem
                              onClick={() => deleteJob(job.id)}
                              className="text-red-600"
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              削除
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* ジョブ詳細ダイアログ */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {selectedJob && getStatusIcon(selectedJob.status)}
              ジョブ詳細: {selectedJob?.id.slice(-8)}
            </DialogTitle>
            <DialogDescription>
              スクレイピングジョブの詳細情報と結果
            </DialogDescription>
          </DialogHeader>

          {selectedJob && (
            <div className="space-y-4">
              {/* 基本情報 */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium">ステータス</label>
                  <div className="mt-1">{getStatusBadge(selectedJob.status)}</div>
                </div>
                <div>
                  <label className="text-sm font-medium">進捗</label>
                  <div className="mt-1 text-sm">
                    {selectedJob.progress} / {selectedJob.total} 
                    ({((selectedJob.progress / selectedJob.total) * 100).toFixed(1)}%)
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">作成日時</label>
                  <div className="mt-1 text-sm">
                    {new Date(selectedJob.created_at).toLocaleString()}
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">完了日時</label>
                  <div className="mt-1 text-sm">
                    {selectedJob.completed_at 
                      ? new Date(selectedJob.completed_at).toLocaleString()
                      : '-'
                    }
                  </div>
                </div>
              </div>

              <Separator />

              {/* 処理結果 */}
              <div className="space-y-3">
                <h4 className="font-medium">処理結果</h4>
                
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-lg font-bold text-green-600">
                      {selectedJob.completed_urls?.length || 0}
                    </div>
                    <div className="text-sm text-muted-foreground">成功</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold text-red-600">
                      {selectedJob.failed_urls?.length || 0}
                    </div>
                    <div className="text-sm text-muted-foreground">失敗</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold text-blue-600">
                      {selectedJob.created_articles?.length || 0}
                    </div>
                    <div className="text-sm text-muted-foreground">作成記事</div>
                  </div>
                </div>

                {/* 失敗詳細 */}
                {selectedJob.failed_urls && selectedJob.failed_urls.length > 0 && (
                  <div className="space-y-2">
                    <h5 className="text-sm font-medium text-red-600">失敗したURL:</h5>
                    <div className="max-h-32 overflow-y-auto space-y-1 text-sm">
                      {selectedJob.failed_urls.map((item, index) => (
                        <div key={index} className="p-2 bg-red-50 rounded border">
                          <div className="font-mono text-xs">{item.url}</div>
                          <div className="text-red-600 text-xs mt-1">{item.error}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 作成記事一覧 */}
                {selectedJob.created_articles && selectedJob.created_articles.length > 0 && (
                  <div className="space-y-2">
                    <h5 className="text-sm font-medium text-blue-600">作成された記事:</h5>
                    <div className="flex flex-wrap gap-1">
                      {selectedJob.created_articles.map((articleId, index) => (
                        <Badge key={index} variant="secondary" className="text-xs">
                          #{articleId.slice(-8)}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};
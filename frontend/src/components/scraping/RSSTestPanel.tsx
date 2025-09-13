import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
// import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import { Loader2, FileText, Brain, Calendar, Clock, ExternalLink, CheckCircle2, XCircle, StopCircle } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';

interface ArxivPaper {
  title: string;
  url: string;
  published_date: string;
  categories: string[];
  authors: string[];
}

interface RSSTestResult {
  message: string;
  file_path: string;
  feeds_processed: number;
  feeds_success: number;
  feeds_failed: number;
  unique_article_urls: number;
  arxiv_enabled: boolean;
  arxiv_papers_found?: number;
  arxiv_papers?: ArxivPaper[];
  sample_urls: string[];
}

interface JobStatus {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  total: number;
  completed_urls: string[];
  failed_urls: Array<{ url: string; error: string }>;
  skipped_urls: string[];
  created_articles: string[];
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export const RSSTestPanel: React.FC = () => {
  const { token } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [rssFilePath, setRssFilePath] = useState((import.meta as any).env.VITE_RSS_FILE_PATH || '/Users/tsutsuikana/Desktop/coding_workspace/news_check_app/backend/rss_feeds.txt');
  const [includeArxiv, setIncludeArxiv] = useState(false);
  const [arxivCategories, setArxivCategories] = useState('cs.AI,cs.LG,cs.CV');
  const [arxivMaxResults, setArxivMaxResults] = useState(10);
  const [hoursBack, setHoursBack] = useState(24);
  const [testResult, setTestResult] = useState<RSSTestResult | null>(null);
  const [scrapingJobId, setScrapingJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [isScrapingInProgress, setIsScrapingInProgress] = useState(false);

  // ジョブ進捗取得
  const fetchJobStatus = useCallback(async (jobId: string) => {
    try {
      const response = await fetch(`/api/scrape/jobs/${jobId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const status: JobStatus = await response.json();
      setJobStatus(status);

      // 完了時の処理
      if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
        setIsScrapingInProgress(false);
        if (status.status === 'completed') {
          toast.success(`スクレイピングが完了しました！${status.created_articles.length}件の記事を作成しました`);
        } else if (status.status === 'failed') {
          toast.error('スクレイピングが失敗しました');
        } else if (status.status === 'cancelled') {
          toast.warning('スクレイピングがキャンセルされました');
        }
      }
    } catch (err) {
      console.error('Failed to fetch job status:', err);
      toast.error('進捗の取得に失敗しました');
    }
  }, [token]);

  // ジョブキャンセル
  const handleJobCancel = useCallback(async (jobId: string) => {
    try {
      const response = await fetch(`/api/scrape/jobs/${jobId}/cancel`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('キャンセルに失敗しました');
      }

      toast.success('ジョブをキャンセルしました');
      setIsScrapingInProgress(false);
      return true;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'キャンセルに失敗しました';
      toast.error(errorMessage);
      return false;
    }
  }, [token]);

  // 定期的な進捗更新
  useEffect(() => {
    if (!scrapingJobId || !isScrapingInProgress) return;

    fetchJobStatus(scrapingJobId);
    const interval = setInterval(() => {
      fetchJobStatus(scrapingJobId);
    }, 2000); // 2秒間隔で更新

    return () => clearInterval(interval);
  }, [scrapingJobId, isScrapingInProgress, fetchJobStatus]);

  // RSS + arXiv テスト
  const handleTestRSSFeeds = async () => {
    setIsLoading(true);
    setTestResult(null);
    
    try {
      const body = {
        rss_file_path: rssFilePath,
        include_arxiv: includeArxiv,
        arxiv_categories: includeArxiv ? arxivCategories.split(',').map(c => c.trim()) : [],
        arxiv_max_results: includeArxiv ? arxivMaxResults : 0,
        hours_back: hoursBack
      };
      
      const response = await fetch('/api/rss/feeds/from-file', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data: RSSTestResult = await response.json();
      setTestResult(data);
      toast.success(`テスト完了: ${data.unique_article_urls}件のURLを取得`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'テストに失敗しました';
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  // arXivのみテスト
  const handleTestArxivOnly = async () => {
    setIsLoading(true);
    setTestResult(null);
    
    try {
      const response = await fetch('/api/rss/arxiv/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          categories: arxivCategories.split(',').map(c => c.trim()),
          max_results: arxivMaxResults,
          days_back: 3
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('arXiv API response:', data);
      toast.success(`arXiv検索完了: ${data.papers_returned}件の論文を取得`);
      
      // arXiv結果を表示用に変換
      const arxivResult: RSSTestResult = {
        message: data.message,
        file_path: 'arXiv API',
        feeds_processed: 1,
        feeds_success: 1,
        feeds_failed: 0,
        unique_article_urls: data.papers_returned,
        arxiv_enabled: true,
        arxiv_papers_found: data.papers_returned,
        arxiv_papers: data.papers || [],
        sample_urls: data.papers ? data.papers.slice(0, 5).map((p: ArxivPaper) => p.url) : []
      };
      
      setTestResult(arxivResult);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'arXiv検索に失敗しました';
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  // 手動スクレイピング実行
  const handleStartScraping = async () => {
    if (!testResult) {
      toast.error('まずRSSテストを実行してください');
      return;
    }

    setIsLoading(true);
    
    try {
      const response = await fetch('/api/rss/scrape/manual', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          rss_file_path: rssFilePath,
          auto_generate_tags: true,
          skip_duplicates: true,
          include_arxiv: includeArxiv,
          arxiv_categories: includeArxiv ? arxivCategories.split(',').map(c => c.trim()) : [],
          arxiv_max_results: includeArxiv ? arxivMaxResults : 0,
          hours_back: hoursBack
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setScrapingJobId(data.task_id);
      setIsScrapingInProgress(true);
      setJobStatus(null);
      toast.success(`スクレイピングを開始しました (Task ID: ${data.task_id})`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'スクレイピング開始に失敗しました';
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 設定パネル */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            RSS + arXiv テスト設定
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4">
            <div>
              <label htmlFor="rss-file-path" className="block text-sm font-medium mb-2">
                RSSファイルパス
              </label>
              <input
                id="rss-file-path"
                type="text"
                value={rssFilePath}
                onChange={(e) => setRssFilePath(e.target.value)}
                placeholder="RSSフィードリストファイルのパス"
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* 時間設定セクション */}
            <div className="border border-blue-200 rounded-lg p-4 bg-blue-50">
              <div className="flex items-center gap-2 mb-3">
                <Clock className="h-5 w-5 text-blue-600" />
                <h3 className="text-lg font-semibold text-blue-800">取得時間範囲設定</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="hours-back" className="block text-sm font-medium mb-2 text-blue-700">
                    遡る時間（時間）
                  </label>
                  <input
                    id="hours-back"
                    type="number"
                    min="1"
                    max="168"
                    value={hoursBack}
                    onChange={(e) => setHoursBack(parseInt(e.target.value) || 24)}
                    className="w-full px-3 py-2 border border-blue-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                  />
                  {/* プリセットボタン */}
                  <div className="flex flex-wrap gap-2 mt-2">
                    {[24, 48, 72, 120, 168].map((hours) => (
                      <Button
                        key={hours}
                        variant={hoursBack === hours ? "default" : "outline"}
                        size="sm"
                        onClick={() => setHoursBack(hours)}
                        className="text-xs"
                      >
                        {hours === 24 ? '1日' :
                         hours === 48 ? '2日' :
                         hours === 72 ? '3日' :
                         hours === 120 ? '5日' :
                         hours === 168 ? '7日' : `${hours}h`}
                      </Button>
                    ))}
                  </div>
                </div>
                <div className="flex items-center text-sm text-blue-600">
                  <div>
                    <div className="font-medium">現在の設定: {hoursBack}時間</div>
                    <div className="text-xs text-blue-500 mt-1">
                      {hoursBack === 24 ? '過去1日' : 
                       hoursBack === 48 ? '過去2日' :
                       hoursBack === 72 ? '過去3日' :
                       hoursBack <= 168 ? `過去${Math.ceil(hoursBack/24)}日` : '過去7日以上'}
                      の記事を取得します
                    </div>
                    <div className="text-xs text-blue-400 mt-2">
                      <strong>推奨設定:</strong><br/>
                      • 通常: 24時間<br/>
                      • 失敗時: 48-72時間
                    </div>
                  </div>
                </div>
              </div>
              <p className="text-xs text-blue-600 mt-2">
                💡 自動スクレイピングが失敗した場合は、48時間や72時間に設定して過去の記事を取得できます（最大7日間）
              </p>
            </div>

            <div className="flex items-center space-x-3">
              <Checkbox
                id="include-arxiv"
                checked={includeArxiv}
                onCheckedChange={(checked) => setIncludeArxiv(checked === true)}
              />
              <label htmlFor="include-arxiv" className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                <Brain className="h-4 w-4" />
                arXiv論文を含める
              </label>
            </div>

            {includeArxiv && (
              <>
                <div>
                  <label htmlFor="arxiv-categories" className="block text-sm font-medium mb-2">
                    arXivカテゴリ（カンマ区切り）
                  </label>
                  <input
                    id="arxiv-categories"
                    type="text"
                    value={arxivCategories}
                    onChange={(e) => setArxivCategories(e.target.value)}
                    placeholder="cs.AI,cs.LG,cs.CV"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                
                <div>
                  <label htmlFor="arxiv-max-results" className="block text-sm font-medium mb-2">
                    arXiv最大取得件数
                  </label>
                  <input
                    id="arxiv-max-results"
                    type="number"
                    min="1"
                    max="100"
                    value={arxivMaxResults}
                    onChange={(e) => setArxivMaxResults(parseInt(e.target.value) || 10)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </>
            )}
          </div>

          {/* テストボタン */}
          <div className="flex gap-2 pt-4">
            <Button 
              onClick={handleTestRSSFeeds} 
              disabled={isLoading}
              className="flex items-center gap-2"
            >
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              RSS{includeArxiv ? ' + arXiv' : ''}テスト
            </Button>
            
            {includeArxiv && (
              <Button 
                variant="outline"
                onClick={handleTestArxivOnly} 
                disabled={isLoading}
                className="flex items-center gap-2"
              >
                {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Brain className="h-4 w-4" />}
                arXivのみテスト
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* テスト結果 */}
      {testResult && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>テスト結果</span>
              <Button 
                onClick={handleStartScraping}
                disabled={isLoading || !testResult}
                className="flex items-center gap-2"
              >
                {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                スクレイピング実行
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* サマリー */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-3 bg-muted rounded-lg">
                <div className="text-2xl font-bold text-blue-600">{testResult.feeds_success}</div>
                <div className="text-sm text-muted-foreground">成功フィード</div>
              </div>
              <div className="text-center p-3 bg-muted rounded-lg">
                <div className="text-2xl font-bold text-red-600">{testResult.feeds_failed}</div>
                <div className="text-sm text-muted-foreground">失敗フィード</div>
              </div>
              <div className="text-center p-3 bg-muted rounded-lg">
                <div className="text-2xl font-bold text-green-600">{testResult.unique_article_urls}</div>
                <div className="text-sm text-muted-foreground">記事URL</div>
              </div>
              {testResult.arxiv_enabled && (
                <div className="text-center p-3 bg-muted rounded-lg">
                  <div className="text-2xl font-bold text-purple-600">{testResult.arxiv_papers_found || 0}</div>
                  <div className="text-sm text-muted-foreground">arXiv論文</div>
                </div>
              )}
            </div>

            {/* arXiv論文一覧 */}
            {testResult.arxiv_papers && testResult.arxiv_papers.length > 0 && (
              <div>
                <h4 className="font-semibold mb-3 flex items-center gap-2">
                  <Brain className="h-4 w-4" />
                  arXiv論文 ({testResult.arxiv_papers.length}件)
                </h4>
                <div className="space-y-3 max-h-64 overflow-y-auto">
                  {testResult.arxiv_papers.map((paper, index) => (
                    <div key={index} className="p-3 border rounded-lg">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <h5 className="font-medium line-clamp-2">{paper.title}</h5>
                        <a 
                          href={paper.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </div>
                      <div className="flex flex-wrap gap-1 mb-2">
                        {paper.categories.slice(0, 3).map((cat, idx) => (
                          <Badge key={idx} variant="secondary" className="text-xs">
                            {cat}
                          </Badge>
                        ))}
                      </div>
                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {new Date(paper.published_date).toLocaleDateString()}
                        </span>
                        <span>著者: {paper.authors.slice(0, 2).join(', ')}{paper.authors.length > 2 ? ' 他' : ''}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* サンプルURL */}
            <div>
              <h4 className="font-semibold mb-2">サンプルURL (最初の{Math.min(5, testResult.sample_urls.length)}件)</h4>
              <pre className="h-32 overflow-auto p-3 bg-muted rounded text-sm font-mono whitespace-pre-wrap border">
                {testResult.sample_urls.slice(0, 5).join('\n')}
              </pre>
            </div>
          </CardContent>
        </Card>
      )}

      {/* スクレイピング進捗表示 */}
      {isScrapingInProgress && scrapingJobId && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin" />
                スクレイピング進行中
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleJobCancel(scrapingJobId)}
                disabled={isLoading}
                className="flex items-center gap-2"
              >
                <StopCircle className="h-4 w-4" />
                キャンセル
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* ジョブID */}
            <div className="text-sm text-muted-foreground">
              Task ID: {scrapingJobId}
            </div>

            {/* 進捗バー */}
            {jobStatus && (
              <>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>進捗: {jobStatus.progress} / {jobStatus.total}</span>
                    <span>{Math.round((jobStatus.progress / jobStatus.total) * 100)}%</span>
                  </div>
                  <Progress value={(jobStatus.progress / jobStatus.total) * 100} />
                </div>

                {/* ステータス情報 */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center p-3 bg-muted rounded-lg">
                    <div className="text-lg font-semibold text-green-600">{jobStatus.completed_urls.length}</div>
                    <div className="text-xs text-muted-foreground">完了</div>
                  </div>
                  <div className="text-center p-3 bg-muted rounded-lg">
                    <div className="text-lg font-semibold text-red-600">{jobStatus.failed_urls.length}</div>
                    <div className="text-xs text-muted-foreground">失敗</div>
                  </div>
                  <div className="text-center p-3 bg-muted rounded-lg">
                    <div className="text-lg font-semibold text-yellow-600">{jobStatus.skipped_urls?.length || 0}</div>
                    <div className="text-xs text-muted-foreground">スキップ</div>
                  </div>
                  <div className="text-center p-3 bg-muted rounded-lg">
                    <div className="text-lg font-semibold text-blue-600">{jobStatus.created_articles.length}</div>
                    <div className="text-xs text-muted-foreground">記事作成</div>
                  </div>
                </div>

                {/* ステータス */}
                <div className="flex items-center gap-2">
                  {jobStatus.status === 'running' && <Loader2 className="h-4 w-4 animate-spin text-blue-600" />}
                  {jobStatus.status === 'completed' && <CheckCircle2 className="h-4 w-4 text-green-600" />}
                  {jobStatus.status === 'failed' && <XCircle className="h-4 w-4 text-red-600" />}
                  <span className="text-sm capitalize">{jobStatus.status}</span>
                </div>

                {/* 失敗したURL */}
                {jobStatus.failed_urls.length > 0 && (
                  <div className="mt-4">
                    <h4 className="font-medium text-sm mb-2">失敗したURL ({jobStatus.failed_urls.length}件)</h4>
                    <div className="max-h-32 overflow-y-auto space-y-1">
                      {jobStatus.failed_urls.slice(0, 5).map((failed, index) => (
                        <div key={index} className="text-xs bg-red-50 p-2 rounded border-l-2 border-red-200">
                          <div className="font-mono text-red-800 truncate">{failed.url}</div>
                          <div className="text-red-600 mt-1">{failed.error}</div>
                        </div>
                      ))}
                      {jobStatus.failed_urls.length > 5 && (
                        <div className="text-xs text-muted-foreground text-center">
                          ...他 {jobStatus.failed_urls.length - 5} 件
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
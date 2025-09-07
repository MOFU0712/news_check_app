import React, { useState, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { URLInput } from '@/components/scraping/URLInput';
import { ScrapingProgress } from '@/components/scraping/ScrapingProgress';
import { ScrapingHistory } from '@/components/scraping/ScrapingHistory';
import { AutoScheduleSettings } from '@/components/scraping/AutoScheduleSettings.tsx';
import { RSSFeedEditor } from '@/components/scraping/RSSFeedEditor.tsx';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

interface ParsedUrls {
  valid_urls: string[];
  invalid_urls: Array<{ url: string; reason: string }>;
  duplicate_urls: string[];
  summary: {
    valid_count: number;
    invalid_count: number;
    duplicate_count: number;
    total_lines: number;
  };
  estimated_time: string;
}

interface ScrapingJob {
  job_id: string;
  parsed_urls: string[];
  duplicate_urls: string[];
  invalid_urls: Array<{ url: string; reason: string }>;
  estimated_time: string;
}

export const ScrapingPage: React.FC = () => {
  const { user, token } = useAuth();
  const [activeJob, setActiveJob] = useState<ScrapingJob | null>(null);
  const [parsedUrls, setParsedUrls] = useState<ParsedUrls | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // URL解析処理
  const handleUrlParse = useCallback(async (urlsText: string): Promise<ParsedUrls | null> => {
    if (!urlsText.trim()) {
      toast.error('URLを入力してください');
      return null;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/scrape/parse-urls', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ urls_text: urlsText }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data: ParsedUrls = await response.json();
      setParsedUrls(data);
      
      if (data.summary.valid_count === 0) {
        toast.warning('有効なURLが見つかりませんでした');
      } else {
        toast.success(`${data.summary.valid_count}件の有効なURLを検出しました`);
      }

      return data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'URL解析に失敗しました';
      setError(errorMessage);
      toast.error(errorMessage);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  // スクレイピング開始処理
  const handleStartScraping = useCallback(async (
    urlsText: string,
    autoGenerateTags: boolean = true,
    skipDuplicates: boolean = true
  ): Promise<boolean> => {
    if (!parsedUrls || parsedUrls.summary.valid_count === 0) {
      toast.error('まずURLの解析を実行してください');
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/scrape/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          urls_text: urlsText,
          auto_generate_tags: autoGenerateTags,
          skip_duplicates: skipDuplicates,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const job: ScrapingJob = await response.json();
      setActiveJob(job);
      toast.success(`スクレイピングジョブを開始しました (ID: ${job.job_id})`);
      
      return true;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'スクレイピング開始に失敗しました';
      setError(errorMessage);
      toast.error(errorMessage);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [parsedUrls, token]);

  // ジョブ完了時の処理
  const handleJobComplete = useCallback(() => {
    toast.success('スクレイピングが完了しました！');
    setActiveJob(null);
    setParsedUrls(null);
  }, []);

  // ジョブキャンセル処理
  const handleJobCancel = useCallback(async (jobId: string): Promise<boolean> => {
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
      setActiveJob(null);
      return true;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'キャンセルに失敗しました';
      toast.error(errorMessage);
      return false;
    }
  }, [token]);

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Card>
          <CardContent className="p-6">
            <p className="text-muted-foreground">ログインが必要です</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-6 space-y-6">
      {/* ページヘッダー */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">URL スクレイピング</h1>
          <p className="text-muted-foreground mt-2">
            複数のURLから記事を一括取得して保存します
          </p>
        </div>
      </div>

      {/* エラー表示 */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* メインコンテンツ */}
      <Tabs defaultValue="scraping" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="scraping">URL スクレイピング</TabsTrigger>
          <TabsTrigger value="rss">RSS 設定</TabsTrigger>
          <TabsTrigger value="schedule">自動スケジュール</TabsTrigger>
          <TabsTrigger value="history">履歴・管理</TabsTrigger>
        </TabsList>

        {/* スクレイピング実行タブ */}
        <TabsContent value="scraping" className="space-y-6">
          {!activeJob ? (
            /* URL入力画面 */
            <URLInput
              onUrlParse={handleUrlParse}
              onStartScraping={handleStartScraping}
              parsedUrls={parsedUrls}
              isLoading={isLoading}
            />
          ) : (
            /* 進捗表示画面 */
            <ScrapingProgress
              job={activeJob}
              onJobComplete={handleJobComplete}
              onJobCancel={handleJobCancel}
            />
          )}
        </TabsContent>

        {/* RSS設定タブ */}
        <TabsContent value="rss" className="space-y-6">
          <RSSFeedEditor />
        </TabsContent>

        {/* 自動スケジュールタブ */}
        <TabsContent value="schedule" className="space-y-6">
          <AutoScheduleSettings />
        </TabsContent>

        {/* 履歴・管理タブ */}
        <TabsContent value="history" className="space-y-6">
          <ScrapingHistory />
        </TabsContent>
      </Tabs>
    </div>
  );
};
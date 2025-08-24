import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { URLInput } from './URLInput';
import { ScrapingProgress } from './ScrapingProgress';
import { ScrapingHistory } from './ScrapingHistory';

// テスト用のモックデータ
const mockParsedUrls = {
  valid_urls: [
    'https://example.com/article1',
    'https://zenn.dev/sample',
    'https://qiita.com/test'
  ],
  invalid_urls: [
    { url: '無効なURL', reason: 'URL形式が正しくありません' }
  ],
  duplicate_urls: [
    'https://example.com/existing'
  ],
  summary: {
    valid_count: 3,
    invalid_count: 1,
    duplicate_count: 1,
    total_lines: 5
  },
  estimated_time: '約6秒'
};

const mockScrapingJob = {
  job_id: 'test-job-123',
  parsed_urls: ['https://example.com/article1', 'https://zenn.dev/sample'],
  duplicate_urls: ['https://example.com/existing'],
  invalid_urls: [{ url: '無効なURL', reason: 'URL形式が正しくありません' }],
  estimated_time: '約4秒'
};

export const TestScrapingComponents: React.FC = () => {
  const [currentView, setCurrentView] = useState<'input' | 'progress' | 'history'>('input');
  const [parsedUrls, setParsedUrls] = useState(null);
  const [showProgress, setShowProgress] = useState(false);

  // モック関数
  const mockUrlParse = async (urlsText: string) => {
    console.log('Mock URL Parse:', urlsText);
    await new Promise(resolve => setTimeout(resolve, 1000));
    setParsedUrls(mockParsedUrls);
    return mockParsedUrls;
  };

  const mockStartScraping = async (urlsText: string, autoTags: boolean, skipDups: boolean) => {
    console.log('Mock Start Scraping:', { urlsText, autoTags, skipDups });
    await new Promise(resolve => setTimeout(resolve, 500));
    setShowProgress(true);
    return true;
  };

  const mockJobComplete = () => {
    console.log('Mock Job Complete');
    setShowProgress(false);
    setParsedUrls(null);
  };

  const mockJobCancel = async (jobId: string) => {
    console.log('Mock Job Cancel:', jobId);
    await new Promise(resolve => setTimeout(resolve, 500));
    return true;
  };

  return (
    <div className="container mx-auto px-4 py-6 space-y-6">
      {/* ヘッダー */}
      <div>
        <h1 className="text-3xl font-bold">スクレイピングコンポーネント テスト</h1>
        <p className="text-muted-foreground mt-2">
          各コンポーネントの動作をテストできます
        </p>
      </div>

      {/* ナビゲーション */}
      <div className="flex gap-2">
        <Button 
          variant={currentView === 'input' ? 'default' : 'outline'}
          onClick={() => setCurrentView('input')}
        >
          URL入力
        </Button>
        <Button 
          variant={currentView === 'progress' ? 'default' : 'outline'}
          onClick={() => setCurrentView('progress')}
        >
          進捗表示
        </Button>
        <Button 
          variant={currentView === 'history' ? 'default' : 'outline'}
          onClick={() => setCurrentView('history')}
        >
          履歴管理
        </Button>
      </div>

      {/* コンテンツ */}
      {currentView === 'input' && !showProgress && (
        <div>
          <h2 className="text-xl font-semibold mb-4">URL入力コンポーネント</h2>
          <URLInput
            onUrlParse={mockUrlParse}
            onStartScraping={mockStartScraping}
            parsedUrls={parsedUrls}
            isLoading={false}
          />
        </div>
      )}

      {currentView === 'input' && showProgress && (
        <div>
          <h2 className="text-xl font-semibold mb-4">進捗表示コンポーネント</h2>
          <ScrapingProgress
            job={mockScrapingJob}
            onJobComplete={mockJobComplete}
            onJobCancel={mockJobCancel}
          />
        </div>
      )}

      {currentView === 'progress' && (
        <div>
          <h2 className="text-xl font-semibold mb-4">進捗表示コンポーネント（単独）</h2>
          <ScrapingProgress
            job={mockScrapingJob}
            onJobComplete={mockJobComplete}
            onJobCancel={mockJobCancel}
          />
        </div>
      )}

      {currentView === 'history' && (
        <div>
          <h2 className="text-xl font-semibold mb-4">履歴管理コンポーネント</h2>
          <ScrapingHistory />
        </div>
      )}

      {/* UI要素テスト */}
      <Card>
        <CardHeader>
          <CardTitle>UI要素テスト</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <h4 className="font-medium">Progress Bar</h4>
            <Progress value={65} className="w-full" />
          </div>
          
          <div className="space-y-2">
            <h4 className="font-medium">Badges</h4>
            <div className="flex gap-2">
              <Badge variant="outline" className="text-blue-600">待機中</Badge>
              <Badge variant="outline" className="text-yellow-600">実行中</Badge>
              <Badge variant="outline" className="text-green-600">完了</Badge>
              <Badge variant="destructive">失敗</Badge>
              <Badge variant="secondary">キャンセル</Badge>
            </div>
          </div>
          
          <div className="space-y-2">
            <h4 className="font-medium">Buttons</h4>
            <div className="flex gap-2">
              <Button>プライマリ</Button>
              <Button variant="outline">アウトライン</Button>
              <Button variant="secondary">セカンダリ</Button>
              <Button variant="ghost">ゴースト</Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
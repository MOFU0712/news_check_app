import React, { useState, useCallback, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { 
  Clock, 
  Settings, 
  CheckCircle2, 
  AlertCircle,
  Loader2,
  Calendar,
  Bot
} from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';

interface ScheduleConfig {
  user_id: string;
  schedule_time: string;
  enabled: boolean;
  auto_generate_tags: boolean;
  skip_duplicates: boolean;
  include_arxiv: boolean;
  arxiv_categories: string[];
  arxiv_max_results: number;
}

export const AutoScheduleSettings: React.FC = () => {
  const { token } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [currentSchedule, setCurrentSchedule] = useState<ScheduleConfig | null>(null);
  const [scheduleTime, setScheduleTime] = useState({ hour: 2, minute: 0 });
  const [autoGenerateTags, setAutoGenerateTags] = useState(true);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [includeArxiv, setIncludeArxiv] = useState(true);
  const [arxivMaxResults, setArxivMaxResults] = useState(50);

  // 現在のスケジュール設定を取得
  const fetchCurrentSchedule = useCallback(async () => {
    if (!token) return;
    
    try {
      const response = await fetch('/api/rss/schedule', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const schedule: ScheduleConfig = await response.json();
        console.log('Loaded schedule:', schedule); // デバッグログ
        setCurrentSchedule(schedule);
        
        // 時刻をパース
        const [hour, minute] = schedule.schedule_time.split(':').map(Number);
        setScheduleTime({ hour, minute });
        setAutoGenerateTags(schedule.auto_generate_tags);
        setSkipDuplicates(schedule.skip_duplicates);
        setIncludeArxiv(schedule.include_arxiv);
        setArxivMaxResults(schedule.arxiv_max_results);
      } else if (response.status === 404) {
        // スケジュールが設定されていない
        console.log('No schedule found (404)'); // デバッグログ
        setCurrentSchedule(null);
      } else {
        console.error('Failed to fetch schedule:', response.status, response.statusText);
        setCurrentSchedule(null);
      }
    } catch (error) {
      console.error('Failed to fetch current schedule:', error);
      setCurrentSchedule(null);
    }
  }, [token]);

  // 自動スケジュールを設定
  const handleSetupAutoSchedule = useCallback(async () => {
    setIsLoading(true);
    
    try {
      const response = await fetch('/api/rss/auto-schedule', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          hour: scheduleTime.hour,
          minute: scheduleTime.minute,
          auto_generate_tags: autoGenerateTags,
          skip_duplicates: skipDuplicates,
          include_arxiv: includeArxiv,
          arxiv_categories: ['cs.AI', 'cs.LG', 'cs.CV'],
          arxiv_max_results: arxivMaxResults
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      console.log('Schedule setup result:', result); // デバッグログ
      toast.success('自動スケジュールが設定されました！');
      
      // 設定を再取得
      await fetchCurrentSchedule();
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'スケジュール設定に失敗しました';
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [scheduleTime, autoGenerateTags, skipDuplicates, includeArxiv, arxivMaxResults, token, fetchCurrentSchedule]);

  // スケジュールを削除
  const handleDeleteSchedule = useCallback(async () => {
    setIsLoading(true);
    
    try {
      const response = await fetch('/api/rss/schedule', {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      toast.success('自動スケジュールを削除しました');
      setCurrentSchedule(null);
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'スケジュール削除に失敗しました';
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      fetchCurrentSchedule();
    }
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-6">
      {/* 自動スケジュール設定カード */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            自動スケジュール設定
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* 現在の設定状況 */}
          {currentSchedule ? (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                <div className="flex items-center justify-between">
                  <span>
                    自動スケジュールが設定済みです（毎日 {currentSchedule.schedule_time} に実行）
                  </span>
                  <Badge variant="secondary" className="text-green-600">
                    <Calendar className="h-3 w-3 mr-1" />
                    有効
                  </Badge>
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  RSS+arXiv取得 → URL解析 → スクレイピング を自動実行
                </div>
              </AlertDescription>
            </Alert>
          ) : (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                自動スケジュールは設定されていません
              </AlertDescription>
            </Alert>
          )}

          {/* 設定フォーム */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* 実行時刻設定 */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium flex items-center gap-2">
                <Clock className="h-4 w-4" />
                実行時刻
              </h3>
              <div className="flex items-center gap-2">
                <select
                  value={scheduleTime.hour}
                  onChange={(e) => setScheduleTime(prev => ({ ...prev, hour: Number(e.target.value) }))}
                  className="w-20 p-2 border rounded-md"
                >
                  {Array.from({ length: 24 }, (_, i) => (
                    <option key={i} value={i}>
                      {i.toString().padStart(2, '0')}
                    </option>
                  ))}
                </select>
                <span>時</span>
                <select
                  value={scheduleTime.minute}
                  onChange={(e) => setScheduleTime(prev => ({ ...prev, minute: Number(e.target.value) }))}
                  className="w-20 p-2 border rounded-md"
                >
                  {[0, 15, 30, 45].map(minute => (
                    <option key={minute} value={minute}>
                      {minute.toString().padStart(2, '0')}
                    </option>
                  ))}
                </select>
                <span>分</span>
              </div>
              <div className="text-sm text-muted-foreground">
                推奨: 深夜帯（1:00-4:00）にサーバー負荷を分散
              </div>
            </div>

            {/* スクレイピング設定 */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium flex items-center gap-2">
                <Settings className="h-4 w-4" />
                スクレイピング設定
              </h3>
              
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="auto-tags-schedule"
                    checked={autoGenerateTags}
                    onCheckedChange={(checked) => setAutoGenerateTags(checked === true)}
                  />
                  <label htmlFor="auto-tags-schedule" className="text-sm font-medium">
                    自動タグ生成を有効にする
                  </label>
                </div>
                
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="skip-duplicates-schedule"
                    checked={skipDuplicates}
                    onCheckedChange={(checked) => setSkipDuplicates(checked === true)}
                  />
                  <label htmlFor="skip-duplicates-schedule" className="text-sm font-medium">
                    重複URLをスキップする
                  </label>
                </div>
                
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="include-arxiv-schedule"
                    checked={includeArxiv}
                    onCheckedChange={(checked) => setIncludeArxiv(checked === true)}
                  />
                  <label htmlFor="include-arxiv-schedule" className="text-sm font-medium">
                    arXiv論文を含める（50件まで）
                  </label>
                </div>
              </div>
            </div>
          </div>

          {/* 実行内容の説明 */}
          <div className="bg-blue-50 p-4 rounded-lg">
            <h4 className="font-medium mb-2">自動実行される処理</h4>
            <ol className="text-sm space-y-1 text-muted-foreground">
              <li>1. RSS フィードから24時間以内の最新記事を取得</li>
              <li>2. arXiv から3日以内の高品質論文を取得（設定により）</li>
              <li>3. 取得したURLを解析・重複チェック</li>
              <li>4. 有効なURLに対してスクレイピング実行</li>
              <li>5. 記事データベースに保存・自動タグ付け</li>
            </ol>
          </div>

          {/* アクションボタン */}
          <div className="flex gap-4">
            <Button
              onClick={handleSetupAutoSchedule}
              disabled={isLoading}
              className="flex-1"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Bot className="h-4 w-4 mr-2" />
              )}
              {currentSchedule ? 'スケジュール更新' : 'スケジュール設定'}
            </Button>
            
            {currentSchedule && (
              <Button
                variant="outline"
                onClick={handleDeleteSchedule}
                disabled={isLoading}
              >
                スケジュール削除
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
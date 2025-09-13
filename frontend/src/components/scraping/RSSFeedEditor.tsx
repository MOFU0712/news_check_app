import React, { useState, useCallback, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { 
  Settings2, 
  Save, 
  RotateCcw,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ExternalLink,
  Plus
} from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';

interface RSSFeedFileData {
  content: string;
  file_path: string;
}

export const RSSFeedEditor: React.FC = () => {
  const { token } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [originalContent, setOriginalContent] = useState('');
  const [content, setContent] = useState('');
  const [filePath, setFilePath] = useState('');
  const [feedsCount, setFeedsCount] = useState(0);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // RSS フィードファイルを読み込み
  const loadRSSFeedsFile = useCallback(async () => {
    setIsLoading(true);
    
    try {
      const response = await fetch('/api/rss/feeds/file', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data: RSSFeedFileData = await response.json();
      setContent(data.content);
      setOriginalContent(data.content);
      setFilePath(data.file_path);
      setHasUnsavedChanges(false);
      
      // フィード数をカウント
      const feedCount = countValidFeeds(data.content);
      setFeedsCount(feedCount);
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'RSSフィードファイルの読み込みに失敗しました';
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  // RSS フィードファイルを保存
  const saveRSSFeedsFile = useCallback(async () => {
    setIsSaving(true);
    
    try {
      const response = await fetch('/api/rss/feeds/file', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          content: content,
          file_path: filePath
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      setOriginalContent(content);
      setHasUnsavedChanges(false);
      setFeedsCount(result.feeds_count);
      
      toast.success(`RSSフィードファイルを保存しました（${result.feeds_count}件のフィード）`);
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'RSSフィードファイルの保存に失敗しました';
      toast.error(errorMessage);
    } finally {
      setIsSaving(false);
    }
  }, [content, filePath, token]);

  // 変更をリセット
  const resetChanges = useCallback(() => {
    setContent(originalContent);
    setHasUnsavedChanges(false);
    setFeedsCount(countValidFeeds(originalContent));
    toast.info('変更をリセットしました');
  }, [originalContent]);

  // 有効なフィード数をカウント
  const countValidFeeds = useCallback((text: string): number => {
    const lines = text.split('\n');
    let count = 0;
    
    for (const line of lines) {
      const trimmedLine = line.trim();
      if (trimmedLine && !trimmedLine.startsWith('#') && trimmedLine.startsWith('http')) {
        count++;
      }
    }
    
    return count;
  }, []);

  // コンテンツ変更ハンドラ
  const handleContentChange = useCallback((value: string) => {
    setContent(value);
    setHasUnsavedChanges(value !== originalContent);
    setFeedsCount(countValidFeeds(value));
  }, [originalContent, countValidFeeds]);

  // サンプルフィードを追加
  const addSampleFeeds = useCallback(() => {
    const sampleFeeds = [
      '',
      '# 新しく追加されたフィード',
      'https://example-tech-blog.com/feed',
      'https://another-news-site.com/rss',
      ''
    ].join('\n');
    
    const newContent = content + sampleFeeds;
    handleContentChange(newContent);
    toast.info('サンプルフィードを追加しました');
  }, [content, handleContentChange]);

  // ページ読み込み時にファイルを読み込み
  useEffect(() => {
    loadRSSFeedsFile();
  }, [loadRSSFeedsFile]);

  // ページを離れる前に未保存の変更を警告
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        <span>RSSフィードファイルを読み込み中...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* RSS フィード編集カード */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings2 className="h-5 w-5" />
            RSS フィード設定
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* ファイル情報 */}
          <div className="flex items-center justify-between bg-gray-50 p-3 rounded-lg">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              <span className="text-sm font-medium">
                {filePath ? filePath.split('/').pop() : 'rss_feeds.txt'}
              </span>
            </div>
            <div className="flex items-center gap-4">
              <Badge variant="secondary">
                {feedsCount}件のフィード
              </Badge>
              {hasUnsavedChanges && (
                <Badge variant="outline" className="text-amber-600">
                  <AlertTriangle className="h-3 w-3 mr-1" />
                  未保存
                </Badge>
              )}
            </div>
          </div>

          {/* 操作説明 */}
          <Alert>
            <CheckCircle2 className="h-4 w-4" />
            <AlertDescription>
              <div className="space-y-1 text-sm">
                <p><strong>編集方法:</strong></p>
                <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                  <li>各行に1つのRSSフィードURLを記載</li>
                  <li># で始まる行はコメント（無視されます）</li>
                  <li>空行も無視されます</li>
                  <li>https:// または http:// で始まるURLのみ有効</li>
                </ul>
              </div>
            </AlertDescription>
          </Alert>

          {/* テキストエリア */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">
                RSS フィード URL リスト
              </label>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={addSampleFeeds}
                  disabled={isSaving}
                >
                  <Plus className="h-3 w-3 mr-1" />
                  サンプル追加
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadRSSFeedsFile}
                  disabled={isLoading || isSaving}
                >
                  <RotateCcw className="h-3 w-3 mr-1" />
                  再読み込み
                </Button>
              </div>
            </div>
            <Textarea
              value={content}
              onChange={(e) => handleContentChange(e.target.value)}
              className="min-h-[400px] font-mono text-sm"
              placeholder="RSSフィードURLを入力してください..."
              disabled={isSaving}
            />
          </div>

          {/* 統計情報 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-gray-50 p-4 rounded-lg">
            <div className="text-center">
              <div className="text-lg font-bold text-blue-600">
                {feedsCount}
              </div>
              <div className="text-xs text-muted-foreground">有効フィード</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-gray-600">
                {content.split('\n').length}
              </div>
              <div className="text-xs text-muted-foreground">総行数</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-gray-600">
                {content.split('\n').filter(line => line.trim().startsWith('#')).length}
              </div>
              <div className="text-xs text-muted-foreground">コメント行</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-gray-600">
                {content.length}
              </div>
              <div className="text-xs text-muted-foreground">文字数</div>
            </div>
          </div>

          {/* アクションボタン */}
          <div className="flex gap-4">
            <Button
              onClick={saveRSSFeedsFile}
              disabled={!hasUnsavedChanges || isSaving}
              className="flex-1"
            >
              {isSaving ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              設定を保存
            </Button>
            
            {hasUnsavedChanges && (
              <Button
                variant="outline"
                onClick={resetChanges}
                disabled={isSaving}
              >
                <RotateCcw className="h-4 w-4 mr-2" />
                リセット
              </Button>
            )}
          </div>

          {/* 次回取得予告 */}
          <div className="bg-blue-50 p-4 rounded-lg">
            <h4 className="font-medium mb-2 flex items-center gap-2">
              <ExternalLink className="h-4 w-4" />
              次回自動取得時の動作
            </h4>
            <p className="text-sm text-muted-foreground">
              保存された設定は次回の自動スケジュール実行時（設定時刻）または手動「RSS+arXiv取得」時に適用されます。
              現在設定されている{feedsCount}件のフィードから24時間以内の最新記事を取得します。
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
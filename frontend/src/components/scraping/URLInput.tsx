import React, { useState, useCallback, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Loader2, 
  FileText, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Copy,
  Trash2,
  Info,
  Play
} from 'lucide-react';
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

interface URLInputProps {
  onUrlParse: (urlsText: string) => Promise<ParsedUrls | null>;
  onStartScraping: (
    urlsText: string, 
    autoGenerateTags: boolean, 
    skipDuplicates: boolean
  ) => Promise<boolean>;
  parsedUrls: ParsedUrls | null;
  isLoading: boolean;
}

export const URLInput: React.FC<URLInputProps> = ({
  onUrlParse,
  onStartScraping,
  parsedUrls,
  isLoading
}) => {
  const [urlsText, setUrlsText] = useState('');
  const [autoGenerateTags, setAutoGenerateTags] = useState(true);
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // URL解析処理
  const handleParse = useCallback(async () => {
    await onUrlParse(urlsText);
  }, [urlsText, onUrlParse]);

  // スクレイピング開始処理
  const handleStart = useCallback(async () => {
    const success = await onStartScraping(urlsText, autoGenerateTags, skipDuplicates);
    if (success) {
      // 成功時は入力をクリア
      setUrlsText('');
      setSelectedUrls(new Set());
    }
  }, [urlsText, autoGenerateTags, skipDuplicates, onStartScraping]);

  // サンプルURLの挿入
  const insertSampleUrls = useCallback(() => {
    const samples = [
      'https://example.com/article1',
      '- https://zenn.dev/sample-article',
      '- https://qiita.com/example-post',
      'https://dev.to/sample-tutorial',
    ].join('\n');
    
    setUrlsText(samples);
    toast.info('サンプルURLを挿入しました');
  }, []);

  // テキストエリアのクリア
  const clearTextArea = useCallback(() => {
    setUrlsText('');
    setSelectedUrls(new Set());
    toast.info('入力をクリアしました');
  }, []);

  // クリップボードから貼り付け
  const pasteFromClipboard = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setUrlsText(prev => prev + (prev ? '\n' : '') + text);
        toast.success('クリップボードから貼り付けました');
      }
    } catch (err) {
      toast.error('クリップボードの読み取りに失敗しました');
    }
  }, []);

  // URL選択の切り替え
  const toggleUrlSelection = useCallback((url: string) => {
    setSelectedUrls(prev => {
      const newSet = new Set(prev);
      if (newSet.has(url)) {
        newSet.delete(url);
      } else {
        newSet.add(url);
      }
      return newSet;
    });
  }, []);

  // 選択したURLを削除
  const removeSelectedUrls = useCallback(() => {
    if (selectedUrls.size === 0) {
      toast.warning('削除するURLを選択してください');
      return;
    }

    const lines = urlsText.split('\n');
    const filteredLines = lines.filter(line => {
      // 各行からURLを抽出して、選択されたURLに含まれていないかチェック
      const urlMatch = line.match(/https?:\/\/[^\s\]]+/);
      return !urlMatch || !selectedUrls.has(urlMatch[0]);
    });

    setUrlsText(filteredLines.join('\n'));
    setSelectedUrls(new Set());
    toast.success(`${selectedUrls.size}件のURLを削除しました`);
  }, [urlsText, selectedUrls]);

  return (
    <div className="space-y-6">
      {/* URL入力カード */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            URL 入力
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 操作ボタン */}
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={insertSampleUrls}
              disabled={isLoading}
            >
              サンプル挿入
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={pasteFromClipboard}
              disabled={isLoading}
            >
              <Copy className="h-4 w-4 mr-1" />
              貼り付け
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={clearTextArea}
              disabled={isLoading}
            >
              <Trash2 className="h-4 w-4 mr-1" />
              クリア
            </Button>
          </div>

          {/* テキストエリア */}
          <div className="space-y-2">
            <Textarea
              ref={textareaRef}
              placeholder={`URLを入力してください（複数行対応）

サポート形式：
• https://example.com/article1
• - https://example.com/article2
• * https://example.com/article3

最大100件まで処理可能です`}
              value={urlsText}
              onChange={(e) => setUrlsText(e.target.value)}
              className="min-h-[200px] font-mono text-sm"
              disabled={isLoading}
            />
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>{urlsText.split('\n').length} 行</span>
              <span>{urlsText.length} 文字</span>
            </div>
          </div>

          {/* 設定オプション */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="auto-tags"
                checked={autoGenerateTags}
                onCheckedChange={setAutoGenerateTags}
                disabled={isLoading}
              />
              <label htmlFor="auto-tags" className="text-sm font-medium">
                自動タグ生成を有効にする
              </label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="skip-duplicates"
                checked={skipDuplicates}
                onCheckedChange={setSkipDuplicates}
                disabled={isLoading}
              />
              <label htmlFor="skip-duplicates" className="text-sm font-medium">
                重複URLをスキップする
              </label>
            </div>
          </div>

          {/* 解析ボタン */}
          <Button
            onClick={handleParse}
            disabled={!urlsText.trim() || isLoading}
            className="w-full"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <CheckCircle2 className="h-4 w-4 mr-2" />
            )}
            URL を解析
          </Button>
        </CardContent>
      </Card>

      {/* 解析結果表示 */}
      {parsedUrls && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Info className="h-5 w-5" />
                解析結果
              </span>
              <div className="flex items-center gap-2 text-sm font-normal">
                <Clock className="h-4 w-4" />
                <span>推定処理時間: {parsedUrls.estimated_time}</span>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* サマリー */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {parsedUrls.summary.valid_count}
                </div>
                <div className="text-sm text-muted-foreground">有効URL</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-600">
                  {parsedUrls.summary.invalid_count}
                </div>
                <div className="text-sm text-muted-foreground">無効URL</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-yellow-600">
                  {parsedUrls.summary.duplicate_count}
                </div>
                <div className="text-sm text-muted-foreground">重複URL</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {parsedUrls.summary.total_lines}
                </div>
                <div className="text-sm text-muted-foreground">総行数</div>
              </div>
            </div>

            <Separator />

            {/* 有効URLリスト */}
            {parsedUrls.valid_urls.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium text-green-600 flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4" />
                    有効なURL ({parsedUrls.valid_urls.length}件)
                  </h4>
                  {selectedUrls.size > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={removeSelectedUrls}
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      選択したURLを削除 ({selectedUrls.size})
                    </Button>
                  )}
                </div>
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {parsedUrls.valid_urls.map((url, index) => (
                    <div
                      key={`${url}-${index}`}
                      className={`flex items-center space-x-2 p-2 rounded border ${
                        selectedUrls.has(url) ? 'bg-blue-50 border-blue-200' : ''
                      }`}
                    >
                      <Checkbox
                        checked={selectedUrls.has(url)}
                        onCheckedChange={() => toggleUrlSelection(url)}
                      />
                      <code className="flex-1 text-xs bg-gray-50 px-2 py-1 rounded">
                        {url}
                      </code>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 重複URLリスト */}
            {parsedUrls.duplicate_urls.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium text-yellow-600 flex items-center gap-2">
                  <XCircle className="h-4 w-4" />
                  重複URL ({parsedUrls.duplicate_urls.length}件)
                </h4>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {parsedUrls.duplicate_urls.map((url, index) => (
                    <div key={index} className="flex items-center space-x-2">
                      <Badge variant="secondary" className="text-xs">重複</Badge>
                      <code className="flex-1 text-xs">{url}</code>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 無効URLリスト */}
            {parsedUrls.invalid_urls.length > 0 && (
              <div className="space-y-2">
                <h4 className="font-medium text-red-600 flex items-center gap-2">
                  <XCircle className="h-4 w-4" />
                  無効URL ({parsedUrls.invalid_urls.length}件)
                </h4>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {parsedUrls.invalid_urls.map((item, index) => (
                    <div key={index} className="space-y-1">
                      <code className="text-xs">{item.url}</code>
                      <p className="text-xs text-red-600 ml-4">{item.reason}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* スクレイピング開始ボタン */}
            {parsedUrls.summary.valid_count > 0 && (
              <Button
                onClick={handleStart}
                disabled={isLoading}
                className="w-full"
                size="lg"
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Play className="h-4 w-4 mr-2" />
                )}
                スクレイピングを開始 ({parsedUrls.summary.valid_count}件)
              </Button>
            )}

            {parsedUrls.summary.valid_count === 0 && (
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  スクレイピング可能な有効なURLがありません。URL形式を確認してください。
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
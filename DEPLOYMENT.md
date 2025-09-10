# ITニュース管理システム デプロイメントガイド

初心者でもわかる、リモートサーバーへのデプロイ完全ガイドです。

## 📋 目次

1. [事前準備](#事前準備)
2. [サーバー選択と準備](#サーバー選択と準備)
3. [ドメイン・SSL設定](#ドメインssl設定)
4. [必要なソフトウェアのインストール](#必要なソフトウェアのインストール)
5. [アプリケーションのデプロイ](#アプリケーションのデプロイ)
6. [セキュリティ設定](#セキュリティ設定)
7. [監視・メンテナンス](#監視メンテナンス)
8. [トラブルシューティング](#トラブルシューティング)

## 🚀 事前準備

### 必要なもの
- **GitHubアカウント** (コードがpush済み)
- **Anthropic APIキー** ([取得方法](#anthropic-apiキーの取得))
- **VPSサーバー** (推奨スペック: CPU 2コア以上、RAM 4GB以上)
- **ドメイン名** (オプション、でも推奨)

### 技術要件
- **フロントエンド**: React 18 + TypeScript + Tailwind CSS
- **バックエンド**: FastAPI + Python 3.11
- **データベース**: PostgreSQL 15
- **キャッシュ**: Redis 7
- **AI**: Anthropic Claude API
- **コンテナ**: Docker + Docker Compose

### Anthropic APIキーの取得

1. [Anthropic Console](https://console.anthropic.com/) にアクセス
2. アカウントを作成またはログイン
3. 「API Keys」から新しいキーを作成
4. キーをメモ（後で使用）

## 🖥️ サーバー選択と準備

### おすすめVPSサービス

#### 初心者向け
- **さくらのVPS** (月額880円～) - 日本語サポート充実
- **ConoHa VPS** (月額678円～) - 管理画面が使いやすい
- **AWS Lightsail** ($5/月～) - 世界最大手

#### 推奨スペック
```
- CPU: 2コア以上
- RAM: 4GB以上
- ストレージ: 50GB以上
- OS: Ubuntu 22.04 LTS
```

### サーバー初期設定

#### 1. サーバーにSSH接続

```bash
# VPSの管理画面からIPアドレスを確認
ssh root@YOUR_SERVER_IP
```

#### 2. システムアップデート

```bash
# パッケージ一覧を更新
apt update

# パッケージを最新版にアップデート
apt upgrade -y
```

#### 3. 必要なパッケージのインストール

```bash
# 基本パッケージ
apt install -y curl wget git vim ufw
```

## 🌐 ドメイン・SSL設定

### ドメインの設定 (オプション)

#### 1. ドメインを取得
- お名前.com、ムームードメインなどで取得

#### 2. DNSレコードの設定
```
タイプ: A
ネーム: @ (または空欄)
コンテンツ: YOUR_SERVER_IP

タイプ: A  
ネーム: www
コンテンツ: YOUR_SERVER_IP
```

### SSL証明書 (Let's Encrypt)

```bash
# Certbotをインストール
apt install -y certbot python3-certbot-nginx

# SSL証明書を取得 (ドメインを持っている場合)
certbot --nginx -d your-domain.com -d www.your-domain.com
```

## 🛠️ 必要なソフトウェアのインストール

### 1. Python環境のセットアップ

```bash
# Python 3.11のインストール
apt update
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# pipのアップグレード
python3.11 -m pip install --upgrade pip

# システム開発ツールのインストール
apt install -y build-essential libpq-dev curl wget git vim
```

### 2. Node.js環境のセットアップ

```bash
# Node.js 18のインストール
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# インストール確認
node --version
npm --version
```

### 3. PostgreSQL 15のインストールと設定

#### PostgreSQLとは？
PostgreSQLは高性能なオープンソースのリレーショナルデータベースです。このアプリケーションのデータ（ユーザー情報、記事データなど）を保存するために必要です。

#### PostgreSQLのインストール

```bash
# PostgreSQL公式リポジトリを追加
sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
apt update

# PostgreSQL 15をインストール
apt install -y postgresql-15 postgresql-client-15

# PostgreSQLサービスを開始・自動起動設定
systemctl start postgresql
systemctl enable postgresql
```

#### PostgreSQLの初期設定

```bash
# postgresユーザーでPostgreSQLにログイン
sudo -u postgres psql
```

PostgreSQL内で以下のコマンドを実行：

```sql
-- アプリケーション用のデータベースユーザーを作成
CREATE USER news_user WITH PASSWORD 'your_secure_password_here';

-- アプリケーション用のデータベースを作成
CREATE DATABASE news_system OWNER news_user;

-- ユーザーに必要な権限を付与
GRANT ALL PRIVILEGES ON DATABASE news_system TO news_user;

-- PostgreSQLから退出
\q
```

#### PostgreSQLアカウントの説明

**PostgreSQLアカウント（ユーザー）とは？**
- データベースにアクセスするためのアカウントです
- Linuxのユーザーアカウントとは別物です
- データベースごとに異なる権限を設定できます

**主要なアカウントの種類：**

1. **postgres** - PostgreSQLの管理者アカウント（自動作成される）
   - データベース全体の管理権限を持つ
   - 新しいユーザーやデータベースを作成できる

2. **news_user**（今回作成） - アプリケーション専用アカウント
   - news_systemデータベースにのみアクセス可能
   - アプリケーションが使用する専用アカウント
   - セキュリティのため、最小限の権限のみ付与

#### PostgreSQL接続テスト

```bash
# 作成したユーザーでデータベースに接続テスト
psql -h localhost -U news_user -d news_system
# パスワードを求められるので、設定したパスワードを入力
# 接続できたら \q で退出
```

### 4. Redis 7のインストール

```bash
# Redis公式リポジトリを追加
curl -fsSL https://packages.redis.io/gpg | gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/redis.list
apt update

# Redisをインストール
apt install -y redis-server

# Redisサービスを開始・自動起動設定
systemctl start redis-server
systemctl enable redis-server

# Redis接続テスト
redis-cli ping
# 「PONG」が返ってくれば成功
```

### 5. Nginxのインストール（リバースプロキシ用）

```bash
apt install -y nginx

# Nginxを起動・自動起動設定
systemctl start nginx
systemctl enable nginx
```

### 6. ファイアウォール設定

```bash
# UFWを有効化
ufw enable

# 必要なポートを開放
ufw allow ssh
ufw allow 80
ufw allow 443

# 設定確認
ufw status
```


## 📦 アプリケーションのデプロイ

### 1. コードの取得

```bash
# アプリケーション用ディレクトリを作成
mkdir -p /opt/news_check_app
cd /opt/news_check_app

# GitHubからクローン（YOUR_USERNAMEを実際のGitHubユーザー名に変更）
git clone https://github.com/YOUR_USERNAME/news_check_app.git .

# ファイル権限を設定
chown -R $USER:$USER /opt/news_check_app
```

### 2. Python仮想環境の作成

```bash
cd /opt/news_check_app

# Python仮想環境を作成
python3.11 -m venv venv

# 仮想環境を有効化
source venv/bin/activate

# Python依存関係をインストール
cd backend
pip install -r requirements.txt
```

### 3. 環境変数の設定

#### バックエンド環境変数

```bash
cd backend
cp .env.example .env
vim .env
```

`.env`ファイルの内容：

```bash
# データベース設定（PostgreSQLサーバーの設定）
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=news_user
POSTGRES_PASSWORD=your_secure_db_password_here
POSTGRES_DB=news_system

# Redis設定（ローカルRedisサーバー）
REDIS_URL=redis://localhost:6379

# セキュリティ設定（必ず変更！）
SECRET_KEY=your_very_secure_secret_key_change_this_to_random_64_chars
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS設定（本番ドメインに変更）
BACKEND_CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com

# 管理者アカウント設定
FIRST_SUPERUSER_EMAIL=admin@your-domain.com
FIRST_SUPERUSER_PASSWORD=your_secure_admin_password

# Anthropic API設定（必須）
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-api-key-here

# 環境設定
ENVIRONMENT=production
DEBUG=false
```

#### フロントエンド環境変数

```bash
cd /opt/news_check_app/frontend
cp .env.example .env
vim .env
```

`.env`ファイルの内容：

```bash
# APIのベースURL（本番環境のドメインに変更）
VITE_API_BASE_URL=https://your-domain.com/api
```

### 4. データベースの初期化

```bash
# バックエンドディレクトリに移動
cd /opt/news_check_app
source venv/bin/activate
cd backend

# データベーステーブルを作成
python create_tables.py

# 管理者ユーザーを作成
python create_new_admin.py
```

## 💾 ローカルデータベースのリモートサーバーへの移行

既にローカル環境でデータベースを構築済みの場合、そのデータをリモートサーバーに移行する方法を説明します。

### 方法1: ダンプ・リストア方式（推奨）

この方法は最も安全で確実です。

#### Step 1: ローカルデータベースのバックアップ作成

**ローカルマシンで実行**:

```bash
# ローカル環境のデータベースをバックアップ
cd /path/to/your/local/news_check_app

# PostgreSQLの場合
pg_dump -h localhost -U news_user -d news_system > local_database_backup.sql

# 圧縮してサイズを小さく（推奨）
gzip local_database_backup.sql
# これで local_database_backup.sql.gz ができます
```

#### Step 2: バックアップファイルをリモートサーバーに転送

```bash
# SCPでファイルをリモートサーバーに転送
scp local_database_backup.sql.gz root@YOUR_SERVER_IP:/opt/news_check_app/

# または、GitHubを経由する場合（小さなファイルの場合のみ）
# 注意：機密データが含まれる可能性があるため、プライベートリポジトリで行うこと
```

#### Step 3: リモートサーバーでのリストア

**リモートサーバーで実行**:

```bash
cd /opt/news_check_app

# バックアップファイルを解凍
gunzip local_database_backup.sql.gz

# リモートサーバーのデータベースを一度空にする（既存テーブルがある場合）
psql -h localhost -U news_user -d news_system -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# バックアップからデータを復元
psql -h localhost -U news_user -d news_system < local_database_backup.sql

# 復元を確認
psql -h localhost -U news_user -d news_system -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"
```

### 方法2: CSV エクスポート・インポート方式

大量のデータがある場合や、特定のテーブルのみ移行したい場合に便利です。

#### Step 1: ローカルからCSVでエクスポート

**ローカルマシンで実行**:

```bash
# 主要なテーブルをCSVでエクスポート
mkdir -p /tmp/db_export

# 例：ユーザーテーブル
psql -h localhost -U news_user -d news_system -c "COPY users TO '/tmp/db_export/users.csv' WITH CSV HEADER;"

# 例：記事テーブル
psql -h localhost -U news_user -d news_system -c "COPY articles TO '/tmp/db_export/articles.csv' WITH CSV HEADER;"

# 他の必要なテーブルも同様に...

# CSVファイルを圧縮
tar -czf db_export.tar.gz -C /tmp db_export/
```

#### Step 2: CSVファイルをリモートサーバーに転送

```bash
# CSVファイルをリモートサーバーに転送
scp db_export.tar.gz root@YOUR_SERVER_IP:/opt/news_check_app/
```

#### Step 3: リモートサーバーでCSVをインポート

**リモートサーバーで実行**:

```bash
cd /opt/news_check_app

# CSVファイルを解凍
tar -xzf db_export.tar.gz

# テーブル構造は既に作成済み（create_tables.pyで作成）
# データのみをインポート

# 例：ユーザーテーブル
psql -h localhost -U news_user -d news_system -c "COPY users FROM '/opt/news_check_app/db_export/users.csv' WITH CSV HEADER;"

# 例：記事テーブル
psql -h localhost -U news_user -d news_system -c "COPY articles FROM '/opt/news_check_app/db_export/articles.csv' WITH CSV HEADER;"

# インポート結果を確認
psql -h localhost -U news_user -d news_system -c "SELECT COUNT(*) FROM users;"
psql -h localhost -U news_user -d news_system -c "SELECT COUNT(*) FROM articles;"
```

### 方法3: 直接データベース間複製（上級者向け）

ネットワーク経由で直接データを複製する方法です。

#### 前提条件の確認

```bash
# リモートサーバーでPostgreSQLがローカルからアクセス可能か確認
# /etc/postgresql/15/main/postgresql.conf で以下を設定:
# listen_addresses = '*'

# /etc/postgresql/15/main/pg_hba.conf にローカルIPからの接続を許可:
# host all all YOUR_LOCAL_IP/32 md5

# PostgreSQLを再起動
systemctl restart postgresql
```

#### ローカルから直接複製

**ローカルマシンで実行**:

```bash
# 直接リモートのデータベースに接続してデータを挿入
pg_dump -h localhost -U news_user -d news_system | psql -h YOUR_SERVER_IP -U news_user -d news_system
```

### 📋 移行後の確認事項

移行完了後、以下を必ず確認してください：

```bash
# リモートサーバーで実行

# 1. テーブル数の確認
psql -h localhost -U news_user -d news_system -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"

# 2. レコード数の確認
psql -h localhost -U news_user -d news_system -c "
SELECT 
    schemaname,
    tablename,
    n_tup_ins AS inserted_rows,
    n_tup_upd AS updated_rows,
    n_tup_del AS deleted_rows
FROM pg_stat_user_tables;
"

# 3. インデックスの確認
psql -h localhost -U news_user -d news_system -c "SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'public';"

# 4. アプリケーションからの接続テスト
cd /opt/news_check_app/backend
source ../venv/bin/activate
python -c "
from app.db.database import SessionLocal
db = SessionLocal()
try:
    result = db.execute('SELECT VERSION()')
    print('Database connection successful!')
    print('PostgreSQL version:', result.fetchone()[0])
finally:
    db.close()
"
```

### 🚨 注意事項とトラブルシューティング

#### 権限エラーが発生した場合

```bash
# PostgreSQLユーザーにスーパーユーザー権限を一時的に付与
sudo -u postgres psql -c "ALTER USER news_user CREATEDB CREATEROLE;"

# 移行完了後は権限を元に戻す
sudo -u postgres psql -c "ALTER USER news_user NOCREATEDB NOCREATEROLE;"
```

#### 文字エンコーディングエラーの場合

```bash
# データベースの文字エンコーディングを確認
psql -h localhost -U news_user -d news_system -c "SHOW SERVER_ENCODING;"

# UTF-8でダンプを作成
pg_dump -h localhost -U news_user -d news_system --encoding=UTF8 > local_database_backup.sql
```

#### 大容量データの場合

```bash
# 並列処理でダンプを高速化
pg_dump -h localhost -U news_user -d news_system -j 4 -Fd -f dump_directory

# 並列処理でリストア
pg_restore -h localhost -U news_user -d news_system -j 4 dump_directory
```

### 5. フロントエンドのビルド

```bash
cd /opt/news_check_app/frontend

# Node.js依存関係をインストール
npm install

# プロダクション用にビルド
npm run build
```

### 6. systemdサービスの作成

#### バックエンドサービス

```bash
vim /etc/systemd/system/news-check-backend.service
```

```ini
[Unit]
Description=News Check App Backend
After=network.target postgresql.service redis-server.service
Requires=postgresql.service redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/news_check_app/backend
Environment=PATH=/opt/news_check_app/venv/bin
ExecStart=/opt/news_check_app/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

#### サービスの有効化と開始

```bash
# systemdの設定をリロード
systemctl daemon-reload

# サービスを有効化・開始
systemctl enable news-check-backend.service
systemctl start news-check-backend.service

# サービスの状態確認
systemctl status news-check-backend.service

# ログ確認
journalctl -u news-check-backend.service -f
```

### 7. Nginxリバースプロキシ設定

#### 本番用Nginx設定ファイルを作成

```bash
vim /etc/nginx/sites-available/news_check_app
```

```nginx
# HTTP用設定（HTTPSへのリダイレクト）
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    
    # HTTPSにリダイレクト
    return 301 https://$server_name$request_uri;
}

# HTTPS用設定
server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL設定 (Let's Encryptで自動設定される)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # セキュリティヘッダー
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # フロントエンド（ビルド済みファイル）
    location / {
        root /opt/news_check_app/frontend/dist;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
        
        # 静的ファイルのキャッシュ設定
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # バックエンドAPI
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # APIのタイムアウト設定
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # ログ設定
    access_log /var/log/nginx/news_check_app.access.log;
    error_log /var/log/nginx/news_check_app.error.log;
}
```

#### 設定を有効化

```bash
# 設定を有効化
ln -s /etc/nginx/sites-available/news_check_app /etc/nginx/sites-enabled/

# Nginxの設定テスト
nginx -t

# Nginxを再起動
systemctl restart nginx
```

### 8. アプリケーションの最終確認

#### サービス状態の確認

```bash
# PostgreSQLサービスの確認
systemctl status postgresql

# Redisサービスの確認
systemctl status redis-server

# バックエンドサービスの確認
systemctl status news-check-backend.service

# Nginxサービスの確認
systemctl status nginx

# 全てが正常に稼働していることを確認
systemctl is-active postgresql redis-server news-check-backend.service nginx
```

#### 接続テスト

```bash
# バックエンドAPIの動作確認
curl -I http://127.0.0.1:8000/api/docs

# フロントエンドの確認（ドメインがある場合）
curl -I https://your-domain.com

# PostgreSQL接続テスト
psql -h localhost -U news_user -d news_system -c "SELECT version();"
```

## 🔒 セキュリティ設定

### 1. 基本セキュリティ強化

#### SSHキー認証の設定

```bash
# ローカルマシンでSSHキーを生成
ssh-keygen -t ed25519 -C "your_email@example.com"

# 公開鍵をサーバーにコピー
ssh-copy-id root@YOUR_SERVER_IP

# SSHパスワード認証を無効化
vim /etc/ssh/sshd_config
```

`/etc/ssh/sshd_config`で以下を編集：
```
PasswordAuthentication no
PermitRootLogin prohibit-password
Port 2222  # デフォルトポートを変更
```

```bash
# SSHサービスを再起動
systemctl restart sshd

# ファイアウォールで新しいSSHポートを開放
ufw allow 2222
ufw delete allow ssh  # 旧ポートを閉じる
```

#### 強力なパスワードとシークレットキーの生成

```bash
# 安全なシークレットキーを生成
openssl rand -hex 32

# パスワード生成コマンド
# Linux/macOS:
head /dev/urandom | tr -dc A-Za-z0-9 | head -c 20

# または、オンラインパスワードジェネレーターを使用
```

### 2. アプリケーションレベルセキュリティ

#### 環境変数のセキュリティ

```bash
# .envファイルの権限を制限
chmod 600 backend/.env frontend/.env

# root以外からの読み取りを禁止
chown root:root backend/.env frontend/.env
```

#### HTTPS強制リダイレクトとHSTS

Nginx設定に追加：
```nginx
# HSTSヘッダーを追加
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

# その他のセキュリティヘッダー
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self';" always;
```

### 3. データベースセキュリティ

```bash
# PostgreSQLの設定を強化
vim /etc/postgresql/15/main/postgresql.conf
# 以下の設定を変更または追加:
# log_statement = 'all'
# log_destination = 'stderr'
# logging_collector = on
# max_connections = 100
# shared_buffers = 256MB

# 設定変更後はPostgreSQLを再起動
systemctl restart postgresql
```

## 📊 監視・メンテナンス

### 1. ログ管理

#### ログローテーション設定

```bash
# logrotate設定ファイルを作成
vim /etc/logrotate.d/news_check_app
```

```bash
/opt/news_check_app/backend/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
}

/var/log/nginx/news_check_app.*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    sharedscripts
    postrotate
        systemctl reload nginx
    endscript
}
```

#### ログ監視スクリプト

```bash
vim /opt/news_check_app/monitor_logs.sh
chmod +x /opt/news_check_app/monitor_logs.sh
```

```bash
#!/bin/bash

# エラーログの監視
ERROR_COUNT=$(tail -n 1000 /var/log/nginx/news_check_app.error.log | grep -c "ERROR")

if [ $ERROR_COUNT -gt 10 ]; then
    echo "エラーが多すぎます: $ERROR_COUNT 件" | mail -s "News Check App Alert" admin@your-domain.com
fi

# ディスク使用量チェック
DISK_USAGE=$(df /opt/news_check_app | awk 'NR==2 {print $5}' | sed 's/%//')

if [ $DISK_USAGE -gt 80 ]; then
    echo "ディスク使用量が高いです: ${DISK_USAGE}%" | mail -s "Disk Usage Alert" admin@your-domain.com
fi
```

#### cronで定期監視

```bash
# cron設定
crontab -e

# 15分ごとにログ監視
*/15 * * * * /opt/news_check_app/monitor_logs.sh

# 毎日深夒2時にデータベースバックアップ
0 2 * * * /opt/news_check_app/backup_database.sh
```

### 2. データベースバックアップ

```bash
vim /opt/news_check_app/backup_database.sh
chmod +x /opt/news_check_app/backup_database.sh
```

```bash
#!/bin/bash

BACKUP_DIR="/opt/backups/news_check_app"
DATE=$(date +%Y%m%d_%H%M%S)

# バックアップディレクトリを作成
mkdir -p $BACKUP_DIR

# データベースバックアップ
pg_dump -h localhost -U news_user -d news_system > $BACKUP_DIR/backup_$DATE.sql

# 古いバックアップを削除（30日以上古いもの）
find $BACKUP_DIR -name "backup_*.sql" -mtime +30 -delete

echo "Backup completed: backup_$DATE.sql"
```

### 3. アプリケーションのヘルスチェック

```bash
vim /opt/news_check_app/health_check.sh
chmod +x /opt/news_check_app/health_check.sh
```

```bash
#!/bin/bash

# バックエンドAPIのヘルスチェック
BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health)

if [ "$BACKEND_STATUS" != "200" ]; then
    echo "バックエンドが応答しません" | mail -s "Backend Down Alert" admin@your-domain.com
    # サービスの再起動を試行
    cd /opt/news_check_app
    systemctl restart news-check-backend.service
fi

# フロントエンドのヘルスチェック
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000)

if [ "$FRONTEND_STATUS" != "200" ]; then
    echo "フロントエンドが応答しません" | mail -s "Frontend Down Alert" admin@your-domain.com
    cd /opt/news_check_app
    # フロントエンドは静的ファイルなので、Nginxのリロードで十分
    systemctl reload nginx
fi
```

### 4. システムリソース監視

```bash
# htopやiostatでリアルタイム監視
apt install -y htop iotop iftop

# システム情報確認コマンド
# CPU・メモリ使用量
htop

# ディスク使用量
df -h

# ネットワーク接続状況
ss -tuln

# アプリケーションプロセスの状況
ps aux | grep -E "(uvicorn|postgres|redis)" | grep -v grep
```

## 🔧 トラブルシューティング

### よくある問題と解決方法

#### 1. API Keyエラー

**エラー例**: `Anthropic API key invalid`

**原因と解決**:
```bash
# 環境変数を確認
cd /opt/news_check_app/backend
source ../venv/bin/activate
python -c "import os; print('ANTHROPIC_API_KEY:', os.environ.get('ANTHROPIC_API_KEY', 'Not found'))"

# からの場合、.envファイルを確認
cat backend/.env | grep ANTHROPIC

# APIキーのテスト
curl -H "Authorization: Bearer YOUR_API_KEY" https://api.anthropic.com/v1/messages
```

#### 2. データベース接続エラー

**エラー例**: `Connection refused` または `Password authentication failed`

**解決手順**:
```bash
# データベースサービスの状況確認
systemctl status postgresql

# データベースログを確認
journalctl -u postgresql -f

# データベースに直接接続テスト
psql -h localhost -U news_user -d news_system

# パスワードが間違っている場合（PostgreSQLユーザーのパスワードを変更）
sudo -u postgres psql -c "ALTER USER news_user PASSWORD 'new_secure_password';"
# 同時に.envファイルのパスワードも更新する必要があります
```

#### 3. CORSエラー

**エラー例**: `Access to fetch at 'api' from origin 'domain' has been blocked by CORS policy`

**解決手順**:
```bash
# バックエンドの.envファイルでCORS設定を確認
cat backend/.env | grep CORS

# 正しい形式例:
# BACKEND_CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com

# フロントエンドの.envファイルでAPI URLを確認
cat frontend/.env | grep VITE_API

# 設定変更後はサービスを再起動
systemctl restart news-check-backend.service
```

#### 4. メモリ不足エラー

**エラー例**: `OOMKilled` または `Memory limit exceeded`

**解決手順**:
```bash
# メモリ使用量確認
free -h
top -u root | grep uvicorn

# systemdサービスでメモリ制限を設定
vim /etc/systemd/system/news-check-backend.service
# [Service]セクションに追加:
# MemoryLimit=1G

# スワップファイルの作成
dd if=/dev/zero of=/swapfile bs=1024 count=2097152
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile swap swap defaults 0 0' >> /etc/fstab
```

#### 5. SSL証明書エラー

**エラー例**: `SSL certificate problem` または `Your connection is not private`

**解決手順**:
```bash
# 証明書の状況確認
certbot certificates

# 証明書の更新
certbot renew --dry-run

# 証明書の再取得
certbot delete --cert-name your-domain.com
certbot --nginx -d your-domain.com -d www.your-domain.com

# Nginx設定のテスト
nginx -t
systemctl restart nginx
```

### ログの確認方法

```bash
# アプリケーションログ

# バックエンドログ
journalctl -u news-check-backend.service -f

# PostgreSQLログ
journalctl -u postgresql -f

# Redisログ
journalctl -u redis-server -f

# Nginxログ
tail -f /var/log/nginx/news_check_app.access.log
tail -f /var/log/nginx/news_check_app.error.log

# システムログ
journalctl -u nginx -f
journalctl -u news-check-backend.service -f
```

### サービスの再起動手順

```bash
# 個別サービスの再起動
systemctl restart news-check-backend.service
systemctl restart postgresql
systemctl restart redis-server
systemctl restart nginx

# 全サービスの再起動
systemctl restart postgresql redis-server news-check-backend.service nginx

# サービス状態の確認
systemctl status postgresql redis-server news-check-backend.service nginx
```

## 🚀 アップデートとメンテナンス

### アプリケーションの更新手順

```bash
cd /opt/news_check_app

# 最新コードを取得
git pull origin main

# Python依存関係を更新（requirements.txtが更新された場合）
source venv/bin/activate
cd backend
pip install -r requirements.txt

# フロントエンドを再ビルド
cd ../frontend
npm install
npm run build

# バックエンドサービスを再起動
systemctl restart news-check-backend.service

# データベースマイグレーション（必要に応じて）
cd /opt/news_check_app/backend
source ../venv/bin/activate
python -m alembic upgrade head
```

### 定期メンテナンスタスク

#### 毎週実行

```bash
# システムアップデート
apt update && apt upgrade -y

# Python仮想環境のパッケージ更新確認
source /opt/news_check_app/venv/bin/activate
pip list --outdated

# Node.jsパッケージ更新確認
cd /opt/news_check_app/frontend
npm outdated
```

#### 毎月実行

```bash
# SSL証明書の有効期限確認
certbot certificates

# ログファイルのサイズ確認
du -sh /var/log/nginx/
du -sh /opt/news_check_app/backend/logs/

# データベースのサイズ確認
psql -h localhost -U news_user -d news_system -c "SELECT pg_size_pretty(pg_database_size('news_system'));"
```

## 📈 パフォーマンス最適化

### データベース最適化

```bash
# データベースの統計情報を更新
psql -h localhost -U news_user -d news_system -c "ANALYZE;"

# データベースのバキューム処理
psql -h localhost -U news_user -d news_system -c "VACUUM ANALYZE;"
```

### スケーリング案

#### 垂直スケーリング (サーバースペックアップ)

- **CPU**: 4コア以上にアップグレード
- **RAM**: 8GB以上にアップグレード
- **ストレージ**: SSDへのアップグレード

#### 水平スケーリング (複数サーバー構成)

1. **ロードバランサー**: Nginxで複数のバックエンドインスタンス
2. **データベース**: 読み書き分離構成
3. **Redis**: クラスタ構成

## 🎆 デプロイ完了後の確認事項

### 1. アプリケーションの動作確認

```bash
# フロントエンドのアクセステスト
curl -I https://your-domain.com

# バックエンドAPIのヘルスチェック
curl -I https://your-domain.com/api/docs

# データベース接続テスト
cd /opt/news_check_app/backend
source ../venv/bin/activate
python -c "from app.db.database import engine; print('Database connection:', engine.connect())"
```

### 2. セキュリティチェック

```bash
# SSL証明書の検証
echo | openssl s_client -connect your-domain.com:443 -servername your-domain.com 2>/dev/null | openssl x509 -noout -dates

# ポートスキャン
nmap -sT -O localhost

# ファイアウォール状況
ufw status verbose
```

### 3. パフォーマンステスト

```bash
# レスポンスタイムテスト
time curl -s https://your-domain.com > /dev/null

# コンカレントアクセステスト
# Apache Benchで簡易負荷テスト
apt install -y apache2-utils
ab -n 100 -c 10 https://your-domain.com/
```

## 🚑 サポートとヘルプ

### ドキュメント
- **README.md**: 基本的な使用方法
- **APIドキュメント**: https://your-domain.com/api/docs

### バグ報告・機能要望
- GitHub Issues: バグ報告・機能要望

### 緊急時の連絡先
本ガイドに記載のメール通知設定を実装して、システム異常時に通知を受け取れるようにしておきましょう。

---

## 🎉 おめでとうございます！

このガイドに従ってデプロイが完了していれば、ITニュース管理システムが本番環境で稼働しているはずです。

### 次のステップ

1. **管理者アカウントでログイン**
2. **初期設定とテストデータの投入**
3. **ユーザーを招待してシステムを本本稼働**

*このデプロイメントガイドは定期的に更新されます。最新版をGitHubで確認してください。*
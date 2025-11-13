# Docker セットアップガイド

このガイドでは、Anaconda から Docker への移行手順を説明します。

## 📋 チェックリスト

- [ ] Docker Desktop がインストールされている
- [ ] GCP サービスアカウントの JSON キーがある
- [ ] Kintone の API トークンがある
- [ ] `.env` ファイルを作成した

## 🚀 クイックスタート（3ステップ）

### Step 1: 環境変数の設定

```powershell
# .env.example をコピー
Copy-Item .env.example .env

# .env を編集して以下を設定：
# - GOOGLE_CLOUD_PROJECT_ID
# - KINTONE_DOMAIN
# - KINTONE_API_TOKEN
# - KINTONE_APP_ID
```

### Step 2: GCP 認証情報の配置

```powershell
# credentials フォルダを作成
New-Item -ItemType Directory -Force -Path credentials

# GCP サービスアカウントの JSON キーを credentials/gcp-key.json として保存
# 例: credentials/gcp-key.json
```

### Step 3: Docker で起動

```powershell
# 初回ビルド＆起動
docker-compose up --build

# または、バックグラウンドで起動
docker-compose up -d --build
```

起動後、以下にアクセス可能：
- Web UI: http://localhost:8000
- Functions: http://localhost:8080

## 📝 詳細な手順

### Docker Desktop のインストール（未インストールの場合）

1. [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop) をダウンロード
2. インストーラーを実行
3. Docker Desktop を起動し、WSL 2 バックエンドを有効化

### GCP サービスアカウントの作成

1. GCP Console で「IAM と管理」→「サービスアカウント」に移動
2. 新しいサービスアカウントを作成
3. 必要な権限を付与：
   - Cloud Storage 管理者
   - Document AI API ユーザー
4. キーを作成（JSON 形式）
5. ダウンロードした JSON ファイルを `credentials/gcp-key.json` として保存

### Kintone API トークンの取得

1. Kintone アプリの設定を開く
2. 「API トークン」タブを選択
3. 新しいトークンを生成
4. 必要な権限を付与：
   - レコード追加
   - レコード閲覧
5. トークンをコピーして `.env` の `KINTONE_API_TOKEN` に設定

## 🔍 トラブルシューティング

### Docker が起動しない

```powershell
# Docker のバージョン確認
docker --version
docker-compose --version

# Docker サービスの状態確認
Get-Service docker
```

### 認証エラー（GCP）

```powershell
# credentials フォルダの確認
Get-ChildItem credentials

# JSON ファイルの内容確認（機密情報に注意）
Get-Content credentials/gcp-key.json
```

### ポートが使用中のエラー

別のアプリケーションが 8000 または 8080 を使用している場合、`docker-compose.yml` のポート番号を変更：

```yaml
services:
  web:
    ports:
      - "9000:8080"  # 8000 → 9000 に変更
```

### ログの確認

```powershell
# リアルタイムでログを表示
docker-compose logs -f

# 特定のサービスのログのみ
docker-compose logs -f functions

# 最新の 100 行のみ表示
docker-compose logs --tail=100
```

### コンテナ内のデバッグ

```powershell
# コンテナ内でシェルを起動
docker-compose exec functions bash

# Python の対話モードで確認
docker-compose exec functions python
>>> import os
>>> os.environ.get('KINTONE_DOMAIN')
```

## 🔄 開発ワークフロー

### コード変更時

Docker Compose は volumes でローカルのコードをマウントしているため、ほとんどの変更は自動反映されます。

```powershell
# ファイルを編集後、変更を確認
docker-compose logs -f functions
```

### requirements.txt 変更時

依存パッケージを追加・更新した場合は再ビルドが必要：

```powershell
docker-compose up --build functions
```

### 完全なクリーンアップ

```powershell
# すべてのコンテナ、ネットワーク、ボリュームを削除
docker-compose down -v

# イメージも削除（完全クリーン）
docker-compose down --rmi all -v
```

## 📊 パフォーマンス比較

| 項目 | Anaconda | Docker |
|------|----------|--------|
| 初回セットアップ | 10-15分 | 5-10分 |
| 起動時間 | 5-10秒 | 10-20秒 |
| メモリ使用量 | 中 | 中〜高 |
| 環境の一貫性 | 低 | 高 |
| デプロイの容易さ | 低 | 高 |

## 🎯 次のステップ

- [ ] ローカルで Web アプリにアクセスして動作確認
- [ ] PDF ファイルをアップロードしてテスト
- [ ] Kintone にデータが正しく追加されるか確認
- [ ] Cloud Run へのデプロイを検討

## 📚 参考リンク

- [Docker 公式ドキュメント](https://docs.docker.com/)
- [Docker Compose リファレンス](https://docs.docker.com/compose/)
- [Google Cloud Functions Framework for Python](https://github.com/GoogleCloudPlatform/functions-framework-python)

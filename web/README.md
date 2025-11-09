# Invoice Uploader (Web App)

Cloud Run で動作する請求書アップロードWebアプリケーション

## 概要

PDFファイルをWebインターフェースからGoogle Cloud Storageにアップロードします。

## ローカル開発

```bash
cd web
python -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
python app.py
```

http://localhost:8080 にアクセス

## デプロイ

GitHub Actionsで自動デプロイされます（main ブランチへのpush時）

または手動デプロイ:

```bash
gcloud run deploy invoice-automation \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --project htbwebsite-chatbot-462005
```

## 環境変数

- `PORT`: アプリケーションのポート番号（デフォルト: 8080）
- `BUCKET_NAME`: アップロード先のGCSバケット名

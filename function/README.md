# Invoice Automation Function

Cloud Functions (Gen2) で動作するDocument AI処理関数

## 概要

Google Cloud Storage にPDFがアップロードされると自動的にトリガーされ、以下を実行:
1. Document AI で請求書を解析
2. 会社マスターと照合
3. Kintone に登録
4. 解析結果をJSON形式でGCSに保存

## ローカル開発

```bash
cd function
python -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# Functions Framework でローカルテスト
export PROJECT_ID=htbwebsite-chatbot-462005
export LOCATION=us
export PROCESSOR_ID=your-processor-id
export KINTONE_DOMAIN=https://your-domain.cybozu.com
export KINTONE_APP_ID=123
export KINTONE_API_TOKEN=your-token

functions-framework --target=on_file_finalized --signature-type=cloudevent
```

## デプロイ

GitHub Actionsで自動デプロイされます（main ブランチへのpush時）

または手動デプロイ:

```bash
gcloud functions deploy invoice-docai-handler \
  --gen2 \
  --runtime python311 \
  --region asia-northeast1 \
  --entry-point on_file_finalized \
  --source . \
  --trigger-bucket htb-energy-contact-center-invoice-input \
  --service-account docai-function-sa@htbwebsite-chatbot-462005.iam.gserviceaccount.com \
  --set-env-vars PROJECT_ID=xxx,LOCATION=us,PROCESSOR_ID=xxx,...
```

## 環境変数

必須:
- `PROJECT_ID`: GCPプロジェクトID
- `LOCATION`: Document AIのロケーション
- `PROCESSOR_ID`: Document AI プロセッサID
- `KINTONE_DOMAIN`: KintoneドメインURL
- `KINTONE_APP_ID`: KintoneアプリID
- `KINTONE_API_TOKEN`: Kintone APIトークン

オプション:
- `OUTPUT_BUCKET`: JSON出力先バケット（デフォルト: htb-energy-contact-center-invoice-output）
- `MASTER_PATH`: 会社マスターJSONのパス

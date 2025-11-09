# 移行ガイド: Option 1 プロジェクト分割

## 🎯 何が変わったか

プロジェクトを **Web App** と **Cloud Function** の2つのディレクトリに分割しました。

## 📂 新しい構造

```
invoice_automation/
├── web/                    # 🆕 Cloud Run用 Webアプリ
│   ├── app.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── README.md
│
├── function/               # 🆕 Cloud Functions用
│   ├── main.py
│   ├── requirements.txt
│   ├── cloudbuild.yaml
│   ├── .gcloudignore
│   ├── functions/
│   │   └── json_saver.py
│   ├── modules/
│   │   ├── document_ai_utils.py
│   │   └── update_kintone_from_docai.py
│   └── README.md
│
├── .github/workflows/
│   ├── deploy-web.yml      # 🆕 Web App専用
│   └── deploy-function.yml # 🆕 Function専用
│
└── [旧ファイル]            # ⚠️ 削除可能（後方互換性のため残存）
    ├── app.py
    ├── main.py
    ├── Dockerfile
    ├── cloudbuild.yaml
    ├── functions/
    └── modules/
```

## ✅ 移行手順

### 1. 既存のデプロイを確認

現在動作しているリソースを確認:

```bash
# Cloud Runサービス
gcloud run services list --region asia-northeast1

# Cloud Functions
gcloud functions list --region asia-northeast1
```

### 2. 新しいワークフローをテスト

#### Web Appのテスト:

```bash
cd web
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
# ブラウザで http://localhost:8080 にアクセス
```

#### Cloud Functionのテスト:

```bash
cd function
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 環境変数を設定
export PROJECT_ID=htbwebsite-chatbot-462005
export LOCATION=us
export PROCESSOR_ID=your-processor-id
export KINTONE_DOMAIN=https://your-domain.cybozu.com
export KINTONE_APP_ID=123
export KINTONE_API_TOKEN=your-token

# ローカルでFunctionsを起動
functions-framework --target=on_file_finalized --signature-type=cloudevent --debug
```

### 3. GitHub Secretsを設定

GitHubリポジトリの Settings → Secrets and variables → Actions で以下を追加:

- `GCP_WIF_PROVIDER` (既存の場合はスキップ)
- `PROCESSOR_ID`
- `KINTONE_DOMAIN`
- `KINTONE_APP_ID`
- `KINTONE_API_TOKEN`

### 4. 古いワークフローを無効化/削除

`.github/workflows/deploy.yml` を削除または無効化:

```bash
# 削除する場合
git rm .github/workflows/deploy.yml

# または名前を変更して無効化
git mv .github/workflows/deploy.yml .github/workflows/deploy.yml.old
```

### 5. 新しい構成でデプロイ

```bash
git add .
git commit -m "feat: プロジェクトをweb/functionに分割"
git push origin main
```

GitHub Actionsが自動的に両方のアプリケーションをデプロイします。

### 6. 動作確認

#### Web App:

```bash
# デプロイされたURLを取得
gcloud run services describe invoice-automation \
  --region asia-northeast1 \
  --format='value(status.url)'

# ブラウザでアクセスして、PDFアップロードをテスト
```

#### Cloud Function:

```bash
# Functionのログを確認
gcloud functions logs read invoice-docai-handler \
  --region asia-northeast1 \
  --limit 50

# テストファイルをアップロード
gsutil cp test.pdf gs://htb-energy-contact-center-invoice-input/
```

### 7. 旧ファイルをクリーンアップ（オプション）

動作確認が完了したら、ルートの旧ファイルを削除:

```bash
git rm app.py main.py Dockerfile cloudbuild.yaml
git rm -r functions/ modules/
git commit -m "chore: 旧ファイルを削除"
git push origin main
```

## 🔍 トラブルシューティング

### Q: デプロイが失敗する

**A**: GitHub Actionsのログを確認:
```bash
# GitHubのリポジトリページ → Actions タブ
```

よくある原因:
- GitHub Secretsが設定されていない
- Workload Identity Federationが正しく設定されていない
- Service Accountの権限不足

### Q: Cloud Functionがトリガーされない

**A**: バケット名とトリガー設定を確認:
```bash
gcloud functions describe invoice-docai-handler \
  --region asia-northeast1 \
  --gen2 \
  --format yaml
```

### Q: import エラーが発生する

**A**: 各ディレクトリの `requirements.txt` を確認:
```bash
cd function
pip install -r requirements.txt
```

## 📊 比較: 旧構成 vs 新構成

| 項目 | 旧構成 | 新構成 |
|------|--------|--------|
| ファイル配置 | ルートに混在 | `/web` と `/function` に分離 |
| 依存関係 | 共有 `requirements.txt` | 各自の `requirements.txt` |
| デプロイ | 1つのワークフロー | 2つの独立したワークフロー |
| Dockerfileの影響 | Cloud Functionsと干渉 | 完全に分離 |
| メンテナンス性 | 低い | 高い |

## 🎉 完了！

新しい構成で、WebアプリとCloud Functionが完全に分離され、それぞれ独立してデプロイできるようになりました。

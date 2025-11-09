# リポジトリ分割ガイド

## 🎯 目的

複数人での開発とWeb UIの拡張に備えて、リポジトリを分割します。

## 📦 新しいリポジトリ構成

1. **invoice-automation-web** - Cloud Run Webアプリケーション
2. **invoice-automation-function** - Cloud Functions バックエンド処理
3. **invoice-automation-shared** (オプション) - 共有スキーマ・設定

## 🔧 分割手順

### 1. GitHub で新しいリポジトリを作成

```bash
# GitHubで以下のリポジトリを作成:
# - invoice-automation-web
# - invoice-automation-function
```

### 2. Web リポジトリの作成

```bash
# 新しいディレクトリで開始
cd ~/Documents
mkdir invoice-automation-web
cd invoice-automation-web

# gitの初期化
git init
git branch -M main

# webディレクトリの内容をコピー
cp -r ../invoice_automation/web/* .
cp ../invoice_automation/web/.dockerignore .

# 専用のGitHub Actionsを配置
mkdir -p .github/workflows
cat > .github/workflows/deploy.yml << 'EOF'
name: Deploy to Cloud Run

on:
  push:
    branches: ["main"]

permissions:
  contents: read
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WIF_PROVIDER }}
          service_account: docai-function-sa@htbwebsite-chatbot-462005.iam.gserviceaccount.com
          project_id: htbwebsite-chatbot-462005

      - uses: google-github-actions/setup-gcloud@v2

      - name: Deploy to Cloud Run
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          project_id: htbwebsite-chatbot-462005
          service: invoice-automation
          region: asia-northeast1
          source: .
          flags: --allow-unauthenticated
EOF

# README を作成
cat > README.md << 'EOF'
# Invoice Automation - Web App

PDFアップロード用のWebアプリケーション（Cloud Run）

## 🚀 クイックスタート

### ローカル開発

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

http://localhost:8080 にアクセス

### デプロイ

mainブランチへのpushで自動デプロイされます。

## 🔗 関連リポジトリ

- [invoice-automation-function](https://github.com/au-aii/invoice-automation-function) - バックエンド処理
EOF

# .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/
.env
.venv/
venv/
*.log
.DS_Store
EOF

# コミット＆プッシュ
git add .
git commit -m "Initial commit: Web app from monorepo split"
git remote add origin git@github.com:au-aii/invoice-automation-web.git
git push -u origin main
```

### 3. Function リポジトリの作成

```bash
# 新しいディレクトリで開始
cd ~/Documents
mkdir invoice-automation-function
cd invoice-automation-function

# gitの初期化
git init
git branch -M main

# functionディレクトリの内容をコピー
cp -r ../invoice_automation/function/* .
cp ../invoice_automation/function/.gcloudignore .

# 専用のGitHub Actionsを配置
mkdir -p .github/workflows
cat > .github/workflows/deploy.yml << 'EOF'
name: Deploy Cloud Function

on:
  push:
    branches: ["main"]

permissions:
  contents: read
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - id: auth
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WIF_PROVIDER }}
          service_account: docai-function-sa@htbwebsite-chatbot-462005.iam.gserviceaccount.com
          project_id: htbwebsite-chatbot-462005

      - uses: google-github-actions/setup-gcloud@v2

      - name: Deploy Cloud Function
        run: |
          gcloud functions deploy invoice-docai-handler \
            --gen2 \
            --runtime python311 \
            --region asia-northeast1 \
            --entry-point on_file_finalized \
            --source . \
            --trigger-bucket htb-energy-contact-center-invoice-input \
            --service-account docai-function-sa@htbwebsite-chatbot-462005.iam.gserviceaccount.com \
            --set-env-vars PROJECT_ID=htbwebsite-chatbot-462005,LOCATION=us,PROCESSOR_ID=${{ secrets.PROCESSOR_ID }},KINTONE_DOMAIN=${{ secrets.KINTONE_DOMAIN }},KINTONE_APP_ID=${{ secrets.KINTONE_APP_ID }},KINTONE_API_TOKEN=${{ secrets.KINTONE_API_TOKEN }},OUTPUT_BUCKET=htb-energy-contact-center-invoice-output
EOF

# README を作成
cat > README.md << 'EOF'
# Invoice Automation - Cloud Function

Document AI処理とKintone連携（Cloud Functions Gen2）

## 🚀 クイックスタート

### ローカル開発

```bash
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

functions-framework --target=on_file_finalized --signature-type=cloudevent
```

### デプロイ

mainブランチへのpushで自動デプロイされます。

## 🔗 関連リポジトリ

- [invoice-automation-web](https://github.com/au-aii/invoice-automation-web) - Webアプリ
EOF

# .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/
.env
.venv/
venv/
*.log
.DS_Store
company_master_2025.json
EOF

# コミット＆プッシュ
git add .
git commit -m "Initial commit: Cloud Function from monorepo split"
git remote add origin git@github.com:au-aii/invoice-automation-function.git
git push -u origin main
```

### 4. 元のリポジトリをアーカイブ（オプション）

```bash
cd ~/Documents/invoice_automation

# READMEを更新してアーカイブ通知
cat > README.md << 'EOF'
# ⚠️ このリポジトリはアーカイブされました

プロジェクトは以下のリポジトリに分割されました:

## 🔗 新しいリポジトリ

- **Web App**: [invoice-automation-web](https://github.com/au-aii/invoice-automation-web)
- **Cloud Function**: [invoice-automation-function](https://github.com/au-aii/invoice-automation-function)

## 📅 分割日

2025年11月9日

## 📜 履歴

このリポジトリの履歴は上記の各リポジトリに引き継がれています。
EOF

git add README.md
git commit -m "docs: アーカイブ通知"
git push origin main

# GitHubでリポジトリをアーカイブ
# Settings → Danger Zone → Archive this repository
```

## ✅ チェックリスト

### リポジトリ作成
- [ ] GitHub で `invoice-automation-web` を作成
- [ ] GitHub で `invoice-automation-function` を作成

### GitHub Secrets 設定（両方のリポジトリに）
- [ ] `GCP_WIF_PROVIDER`
- [ ] `PROCESSOR_ID`
- [ ] `KINTONE_DOMAIN`
- [ ] `KINTONE_APP_ID`
- [ ] `KINTONE_API_TOKEN`

### デプロイ確認
- [ ] Web App が正常にデプロイされる
- [ ] Cloud Function が正常にデプロイされる
- [ ] エンドツーエンドでテスト

### ドキュメント
- [ ] 各リポジトリのREADMEを更新
- [ ] チームメンバーに通知

## 🎯 次のステップ: Web App の拡張

分割後、Webアプリを以下のように拡張できます:

### Next.js への移行例

```bash
cd invoice-automation-web

# Next.js プロジェクトの初期化
npx create-next-app@latest . --typescript --tailwind --app

# 必要なパッケージ
npm install @google-cloud/storage

# Cloud Run 用 Dockerfile 更新
```

### フロントエンド開発環境

- TypeScript
- React/Next.js
- Tailwind CSS
- ESLint / Prettier
- Jest / Testing Library

### バックエンドは安定稼働

Function側は安定したロジックとして、必要最小限の変更のみ。

## 🚨 注意事項

1. **共有データの管理**
   - `company_master_2025.json` は両方で必要
   - Cloud Storage や Secret Manager での管理を推奨

2. **環境変数の同期**
   - バケット名などの変更時は両リポジトリを更新

3. **バージョン管理**
   - セマンティックバージョニングの採用を推奨

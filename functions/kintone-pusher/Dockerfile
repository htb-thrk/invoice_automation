FROM python:3.11-slim

# 作業ディレクトリ設定
WORKDIR /app

# modules をコピー
COPY modules/ /app/modules/

# Cloud Function コードをコピー
COPY functions/kintone-pusher/ /app/

# 依存関係インストール
RUN pip install --no-cache-dir -r requirements.txt

# Cloud Run 用のエントリーポイント設定
ENV PORT=8080
CMD exec functions-framework --target=on_json_finalized --signature-type=cloudevent
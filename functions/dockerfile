# Invoice Automation - Backend Functions
# Cloud Functions エミュレート用または開発/テスト用
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 依存パッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# デフォルトのポート（Functions Framework のデフォルト）
ENV PORT=8080
EXPOSE 8080

# Cloud Functions をローカルで起動（main.py の on_file_finalized を実行）
# 開発時は --debug を追加可能
CMD ["functions-framework", "--target=on_file_finalized", "--signature-type=cloudevent", "--port=8080"]

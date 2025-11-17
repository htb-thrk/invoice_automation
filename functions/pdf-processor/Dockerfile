FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# ✅ 依存関係を先にコピー（Docker キャッシュ活用）
COPY functions/pdf-processor/requirements.txt /app/requirements.txt

# ✅ 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# ✅ modules をコピー
COPY modules/ /app/modules/

# ✅ main.py をコピー
COPY functions/pdf-processor/main.py /app/main.py

# ✅ Cloud Run 用の環境変数
ENV PORT=8080

# ✅ Functions Framework を起動
CMD ["functions-framework", "--target=on_file_finalized", "--signature-type=cloudevent", "--port=8080"]
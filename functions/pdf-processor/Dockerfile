FROM python:3.11-slim

# システムパッケージのインストール（Poppler、Tesseract など）
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-jpn \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリを設定
WORKDIR /app

# ✅ 修正: リポジトリルートから modules をコピー
COPY modules/ /app/modules/

# ✅ 修正: functions/pdf-processor/ から requirements.txt をコピー
COPY functions/pdf-processor/requirements.txt /app/requirements.txt

# 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# ✅ 修正: functions/pdf-processor/ から main.py をコピー
COPY functions/pdf-processor/main.py /app/main.py

# Cloud Run 用のエントリーポイント設定
ENV PORT=8080
CMD exec functions-framework --target=on_file_finalized --signature-type=cloudevent
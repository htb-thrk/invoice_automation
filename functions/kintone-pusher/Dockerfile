FROM python:3.11-slim

WORKDIR /workspace

# 依存パッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# modules ディレクトリをコピー（build context から）
COPY modules /workspace/modules

# 関数コードをコピー
COPY main.py .

# Functions Framework を使用
CMD exec functions-framework --target=on_json_finalized --port=8080
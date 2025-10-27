# functions/main.py
import os
from google.cloud import storage
import functions_framework
from modules.document_ai_utils import process_pdf
from modules.csv_utils import save_daily_csv

# ==== 環境変数 ====
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION", "us")
PROCESSOR_ID = os.environ.get("PROCESSOR_ID")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET", "invoice-csv-output")

# ==== Cloud Functionsトリガー ====
@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    """
    GCSにPDFがアップロードされたときに自動実行される関数
    1. PDFをDocument AIで解析
    2. CSVファイルを出力バケットに保存
    """
    data = cloud_event.data
    bucket = data["bucket"]
    name = data["name"]
    print(f"Triggered by file: gs://{bucket}/{name}")

    try:
        # ① PDF処理
        result = process_pdf(bucket, name)

        # ② CSV出力
        save_daily_csv(result, OUTPUT_BUCKET)

        print("✅ CSV出力完了")
    except Exception as e:
        print(f"[ERROR] {e}")

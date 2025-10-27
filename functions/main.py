# functions/main.py
import os
import json
import traceback
from modules.document_ai_utils import process_pdf
from modules.csv_utils import save_daily_csv
import functions_framework

PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION", "us")
PROCESSOR_ID = os.environ.get("PROCESSOR_ID")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET")

@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    data = cloud_event.data
    bucket = data["bucket"]
    name = data["name"]
    print(f"[INFO] Triggered by file: gs://{bucket}/{name}", flush=True)

    try:
        print("[DEBUG] Starting process_pdf", flush=True)
        result = process_pdf(bucket, name)
        print("[DEBUG] process_pdf finished", flush=True)
        print("[DEBUG] result:", json.dumps(result, ensure_ascii=False), flush=True)

        print("[DEBUG] Calling save_daily_csv", flush=True)
        save_daily_csv(result, OUTPUT_BUCKET)
        print("[DEBUG] Finished save_daily_csv", flush=True)

        print("✅ CSV出力完了", flush=True)

    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}", flush=True)
        print(traceback.format_exc(), flush=True)
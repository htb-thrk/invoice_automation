"""
PDF Processor Cloud Function / Cloud Run
- Cloud Function: イベント駆動（入力: cloud_event）
- Cloud Run: HTTP サーバー（Eventarc 経由でリクエスト受信）
"""
import os
import sys
import json
import logging
import functions_framework
from pathlib import Path
from datetime import datetime

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# modules をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from google.cloud import storage
from modules.docai_processor import process_pdf


@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    """
    Cloud Function エントリーポイント
    Eventarc からのイベントをハンドル
    """
    try:
        # イベントデータのパース
        data = cloud_event.data

        if not data or "bucket" not in data:
            logger.error("❌ Invalid event data: missing bucket or name")
            return

        bucket_name = data.get("bucket")
        file_name = data.get("name")

        logger.info(f"📄 [PDF Processor] Processing: gs://{bucket_name}/{file_name}")

        # PDF ファイルのみ処理
        if not file_name.lower().endswith(".pdf"):
            logger.info(f"⏭️ [PDF Processor] Skipped: {file_name} (not PDF)")
            return

        # 1. Document AI で処理
        extracted_data = process_pdf(bucket_name, file_name)
        logger.info(f"✅ [PDF Processor] Extracted: {extracted_data}")

        # 2. OUTPUT_BUCKET に JSON 保存
        output_bucket_name = os.environ.get("OUTPUT_BUCKET")
        if not output_bucket_name:
            raise ValueError("OUTPUT_BUCKET environment variable is not set")

        storage_client = storage.Client()
        output_bucket = storage_client.bucket(output_bucket_name)
        json_file_name = file_name.replace(".pdf", ".json")
        json_blob = output_bucket.blob(json_file_name)

        # メタデータを追加
        result = {
            **extracted_data,
            "_metadata": {
                "source_file": file_name,
                "source_bucket": bucket_name,
                "processor": "pdf-processor",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }

        json_blob.upload_from_string(
            json.dumps(result, ensure_ascii=False, indent=2),
            content_type="application/json",
        )

        logger.info(f"✅ [PDF Processor] Saved JSON: gs://{output_bucket_name}/{json_file_name}")
        logger.info(f"🎉 [PDF Processor] Successfully processed: {file_name}")

    except Exception as e:
        logger.error(f"❌ [PDF Processor] Error: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    """ローカルテスト用"""
    from dotenv import load_dotenv
    load_dotenv()

    class DummyCloudEvent:
        data = {
            "bucket": os.environ.get("INPUT_BUCKET"),
            "name": "test_invoice.pdf",
        }

    on_file_finalized(DummyCloudEvent())
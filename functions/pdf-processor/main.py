"""
PDF Processor Cloud Function
INPUT_BUCKET に PDF がアップロードされたら実行
Document AI で処理 → JSON を OUTPUT_BUCKET に保存
"""
import os
import sys
import json
from pathlib import Path

# modules をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from google.cloud import storage
from modules.document_ai_utils import process_pdf_from_bytes


def on_file_finalized(cloud_event):
    """
    Cloud Function エントリーポイント
    INPUT_BUCKET への PDF アップロードをトリガー
    """
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]
    
    print(f"📄 [PDF Processor] Processing: gs://{bucket_name}/{file_name}")
    
    # PDF ファイルのみ処理
    if not file_name.lower().endswith(".pdf"):
        print(f"⏭️ [PDF Processor] Skipped: {file_name} (not PDF)")
        return
    
    try:
        # 1. GCS から PDF を取得
        storage_client = storage.Client()
        input_bucket = storage_client.bucket(bucket_name)
        blob = input_bucket.blob(file_name)
        pdf_content = blob.download_as_bytes()
        
        print(f"✅ [PDF Processor] Downloaded: {len(pdf_content)} bytes")
        
        # 2. Document AI で処理
        extracted_data = process_pdf_from_bytes(pdf_content)
        
        print(f"✅ [PDF Processor] Extracted: {extracted_data}")
        
        # 3. OUTPUT_BUCKET に JSON 保存
        output_bucket_name = os.environ.get("OUTPUT_BUCKET")
        if not output_bucket_name:
            raise ValueError("OUTPUT_BUCKET environment variable is not set")
        
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
                "timestamp": json_blob.time_created.isoformat() if json_blob.time_created else None
            }
        }
        
        json_blob.upload_from_string(
            json.dumps(result, ensure_ascii=False, indent=2),
            content_type="application/json"
        )
        
        print(f"✅ [PDF Processor] Saved JSON: gs://{output_bucket_name}/{json_file_name}")
        print(f"🎉 [PDF Processor] Successfully processed: {file_name}")
        
    except Exception as e:
        print(f"❌ [PDF Processor] Error processing {file_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    """ローカルテスト用"""
    from dotenv import load_dotenv
    load_dotenv()
    
    class DummyEvent:
        data = {
            "bucket": os.environ.get("INPUT_BUCKET"),
            "name": "test_invoice.pdf"
        }
    
    on_file_finalized(DummyEvent())
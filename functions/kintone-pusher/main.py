"""
Kintone Pusher Cloud Function
OUTPUT_BUCKET に JSON がアップロードされたら実行
JSON を読み込んで kintone に登録（エラーハンドリング強化版）
"""
import os
import sys
import json
import logging
from pathlib import Path

# modules をパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from google.cloud import storage
from modules.kintone_client import (
    KintoneClient,
    KintoneValidationError,
    KintoneAPIError
)

# ロガー設定
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def on_json_finalized(cloud_event):
    """
    Cloud Function エントリーポイント
    OUTPUT_BUCKET への JSON アップロードをトリガー
    
    Args:
        cloud_event: CloudEvent オブジェクト
    """
    data = cloud_event.data
    bucket_name = data["bucket"]
    file_name = data["name"]
    
    logger.info(f"📝 [Kintone Pusher] Processing: gs://{bucket_name}/{file_name}")
    
    # JSON ファイルのみ処理
    if not file_name.lower().endswith(".json"):
        logger.info(f"⏭️ [Kintone Pusher] Skipped: {file_name} (not JSON)")
        return
    
    try:
        # 1. GCS から JSON を取得
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        
        logger.debug(f"GCS からファイルダウンロード: {file_name}")
        json_text = blob.download_as_text()
        json_data = json.loads(json_text)
        
        logger.info(f"✅ [Kintone Pusher] Loaded JSON: {json_data}")
        
        # 2. kintone クライアント初期化（環境変数から自動取得）
        client = KintoneClient()
        
        # 3. kintone に登録（エラーハンドリング付き）
        try:
            record_id = client.create_record(json_data)
            logger.info(
                f"✅ [Kintone Pusher] Successfully created record: ID={record_id}"
            )
            logger.info(f"🎉 [Kintone Pusher] Successfully processed: {file_name}")
            
        except KintoneValidationError as e:
            # バリデーションエラー: データ不正（リトライ不可）
            logger.error(f"⚠️ [Kintone Pusher] Validation Error: {str(e)}")
            logger.error(f"   File: {file_name}")
            logger.error(f"   Data: {json_data}")
            
            # エラーファイルとして保存（オプション）
            error_bucket_name = os.environ.get("ERROR_BUCKET")
            if error_bucket_name:
                save_error_file(
                    storage_client,
                    error_bucket_name,
                    file_name,
                    json_data,
                    str(e)
                )
            
            # バリデーションエラーは再送不可なので例外を再スローしない
            return
            
        except KintoneAPIError as e:
            # API エラー: リトライ可能な場合がある
            logger.error(f"❌ [Kintone Pusher] Kintone API Error: {str(e)}")
            logger.error(f"   File: {file_name}")
            
            # API エラーは再スローして Cloud Functions のリトライ機構を使う
            raise
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ [Kintone Pusher] Invalid JSON: {str(e)}")
        logger.error(f"   File: {file_name}")
        # JSON パースエラーは再送不可
        return
        
    except Exception as e:
        logger.error(
            f"❌ [Kintone Pusher] Unexpected error: {str(e)}",
            exc_info=True
        )
        # 予期しないエラーは再スロー
        raise


def save_error_file(
    storage_client: storage.Client,
    error_bucket_name: str,
    original_file_name: str,
    json_data: dict,
    error_message: str
) -> None:
    """
    エラーファイルを保存
    
    Args:
        storage_client: GCS クライアント
        error_bucket_name: エラーバケット名
        original_file_name: 元のファイル名
        json_data: JSONデータ
        error_message: エラーメッセージ
    """
    try:
        error_bucket = storage_client.bucket(error_bucket_name)
        error_file_name = f"validation_errors/{original_file_name}"
        error_blob = error_bucket.blob(error_file_name)
        
        error_data = {
            "error": error_message,
            "original_data": json_data,
            "source_file": original_file_name
        }
        
        error_blob.upload_from_string(
            json.dumps(error_data, ensure_ascii=False, indent=2),
            content_type="application/json"
        )
        
        logger.info(
            f"💾 [Kintone Pusher] Saved error details: "
            f"gs://{error_bucket_name}/{error_file_name}"
        )
        
    except Exception as e:
        logger.error(f"⚠️ エラーファイル保存失敗: {str(e)}")


if __name__ == "__main__":
    """ローカルテスト用"""
    from dotenv import load_dotenv
    load_dotenv()
    
    class DummyEvent:
        data = {
            "bucket": os.environ.get("OUTPUT_BUCKET"),
            "name": "test_invoice.json"
        }
    
    on_json_finalized(DummyEvent())
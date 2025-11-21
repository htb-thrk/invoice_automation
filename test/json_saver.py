import os, json
from google.cloud import storage

def save_json_to_gcs(data: dict, bucket_name: str, blob_name: str):
    """Document AI抽出結果をJSONでGCSに保存"""
    storage_client = storage.Client()
    base_name = os.path.splitext(blob_name.split("/")[-1])[0]
    json_blob = f"{base_name}.json"

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(json_blob)
    blob.upload_from_string(json.dumps(data, ensure_ascii=False, indent=2), content_type="application/json")

    print(f"✅ JSON saved to gs://{bucket_name}/{json_blob}")
    return f"gs://{bucket_name}/{json_blob}"

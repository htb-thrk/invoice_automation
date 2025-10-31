import functions_framework
from functions.document_ai_utils import process_pdf
from functions.excel_updater import write_to_sheet
import requests

@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    """GCSトリガーでPDFがアップされたら発火"""
    data = cloud_event.data
    bucket = data["bucket"]
    name = data["name"]

    print(f"Triggered by file: gs://{bucket}/{name}")
    result = process_pdf(bucket, name)
    print("Extracted result:", result)

    write_to_sheet(result)

def post_to_kintone(fields: dict):
    """抽出結果を kintone に書き込む"""
    try:
        domain = os.environ["KINTONE_DOMAIN"]
        app_id = os.environ["KINTONE_APP_ID"]
        token = os.environ["KINTONE_API_TOKEN"]

        url = f"https://{domain}/k/v1/record.json"
        headers = {
            "X-Cybozu-API-Token": token,
            "Content-Type": "application/json"
        }

        record = {
            "小計": {"value": fields.get("amount_excl_tax")},
            "合計": {"value": fields.get("amount_incl_tax")},
            "支払期限": {"value": fields.get("due_date")},
        }

        payload = {"app": app_id, "record": record}
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        print("✅ Kintoneに登録完了:", res.json())
        return True
    except Exception as e:
        print(f"[ERROR] Kintone書き込み失敗: {e}")
        return False
    
        result = process_pdf(bucket, name)
    post_to_kintone(result)   # ← ここを追加
    target_bucket = OUTPUT_BUCKET or bucket
    out_uri = save_json(target_bucket, name, result)
import os
import requests
import functions_framework
from functions.document_ai_utils import process_pdf
from functions.excel_updater import write_to_sheet

# === kintone書き込み関数 ===
def post_to_kintone(fields: dict):
    """抽出結果を kintone に書き込む"""
    try:
        domain = os.environ["KINTONE_DOMAIN"]
        app_id = os.environ["KINTONE_APP_ID"]
        token = os.environ["KINTONE_API_TOKEN"]

        url = f"https://{domain}/k/v1/record.json"
        headers = {
            "X-Cybozu-API-Token": token,
            "Content-Type": "application/json"
        }

        # ✅ 必要項目のみ（ユーザー指定）
        record = {
            "小計": {"value": fields.get("amount_excl_tax")},
            "合計": {"value": fields.get("amount_incl_tax")},
            "進捗": {"value": "承認"},
            "入金期日": {"value": fields.get("due_date")},
        }

        payload = {"app": app_id, "record": record}
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        print("✅ Kintoneに登録完了:", res.json())
        return True
    except Exception as e:
        print(f"[ERROR] Kintone書き込み失敗: {e}")
        return False


# === GCSトリガー本体 ===
@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    """GCSトリガーでPDFがアップされたら発火"""
    data = cloud_event.data
    bucket = data["bucket"]
    name = data["name"]

    print(f"Triggered by file: gs://{bucket}/{name}")

    # Document AIで抽出
    result = process_pdf(bucket, name)
    print("Extracted result:", result)

    # ✅ Kintoneへ書き込み
    post_to_kintone(result)

    # ✅ （必要に応じて）シートにも書き込み
    write_to_sheet(result)

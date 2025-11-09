import os
import json
import re
import functions_framework
from google.cloud import storage
from modules.document_ai_utils import process_pdf
from modules.update_kintone_from_docai import push_from_docai
from functions.json_saver import save_json_to_gcs

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MASTER_PATH = os.path.join(PROJECT_ROOT, "company_master_2025.json")

def normalize_vendor(name: str) -> str:
    if not name:
        return ""
    name = re.sub(r"(株式会社|（株）|㈱)", "", name)
    name = re.sub(r"\s|　", "", name)
    return name.strip()

def classify_company(company_name: str, master_path: str = DEFAULT_MASTER_PATH):
    if not company_name:
        return None
    try:
        with open(master_path, "r", encoding="utf-8") as f:
            master_data = json.load(f)
    except Exception as e:
        print(f"❌ company_master の読込失敗: {e}")
        return None

    normalized_input = normalize_vendor(company_name)
    for entry in master_data:
        vendor = normalize_vendor(entry.get("vendor", ""))
        if vendor and vendor == normalized_input:
            return entry
    return None

@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    data = cloud_event.data
    bucket, name = data["bucket"], data["name"]
    print(f"📄 Triggered by file: gs://{bucket}/{name}")

    try:
        result = process_pdf(bucket, name)
        print(f"✅ Document AI解析完了: {result.get('vendor', '不明な会社')}")

        company_info = classify_company(result.get("vendor"))
        if not company_info:
            print(f"⚠️ 未登録の会社です: {result.get('vendor')}")
            return

        print(f"✅ 該当会社: {company_info['vendor']}")

        # Kintoneへ登録
        push_from_docai(result)
        print("✅ Kintoneへの登録完了")

        # JSON結果を保存
        output_bucket = os.environ.get("OUTPUT_BUCKET", "htb-energy-contact-center-invoice-output")
        out_uri = save_json_to_gcs(result, output_bucket, name)
        print(f"💾 JSONを保存しました: {out_uri}")

    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        raise

    print("✅ 処理完了")

import functions_framework
from modules.document_ai_utils import process_pdf
from modules.kintone_writer import post_to_kintone
from functions.json_saver import save_json

@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    data = cloud_event.data
    bucket, name = data["bucket"], data["name"]
    print(f"Triggered by file: gs://{bucket}/{name}")

    result = process_pdf(bucket, name)

    company_info = classify_company(result.get("company_name"))
    if company_info:
        print("✅ 該当会社:", company_info["company_name"])
        print("📘 転記先テーブル:", company_info["target_table"])
        print("🆔 kintone app id:", company_info["kintone_app_id"])
    else:
        print("⚠️ 未登録の会社ですkintoneで先に登録してください。:", result.get("company"))
    print("Extracted result:", result)

    # kintone へ書き込み
    post_to_kintone(result)
    out_uri = save_json(bucket, name, result)
    print(f"Saved JSON to {out_uri}")

def classify_company(company_name: str, master_path= "company_master.json"):
    """company_master.json をもとに社名に応じた分類情報を返す"""

    if not company_name:
        return None
    
    try:
        with open(master_path, "r", encoding="utf-8") as f:
            master_data = json.load(f)

            for entry in master_data:
                if entry["keyword"] in company_name:
                    return entry
            return None
        
    except Exception as e:
        print(f"Error reading company master: {e}")
        return None
import json
import os
import re
import functions_framework
from google.cloud import storage
from modules.document_ai_utils import process_pdf
from modules.kintone_writer import post_to_kintone
from functions.json_saver import save_json

# === 定数設定 ===
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MASTER_PATH = os.path.join(PROJECT_ROOT, "company_master_2025.json")


# === 共通関数 ===
def normalize_vendor(name: str) -> str:
    """'株式会社' の有無を無視し、空白・全角スペースを除去"""
    if not name:
        return ""
    name = re.sub(r"(株式会社|（株）|㈱)", "", name)
    name = re.sub(r"\s|　", "", name)
    return name.strip()


def classify_company(company_name: str, master_path: str = DEFAULT_MASTER_PATH):
    """company_master_2025.json をもとに社名に応じた分類情報を返す"""
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


# === メイン関数（Cloud Functionsトリガー） ===
@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    """Document AI のPDF解析後にGCSファイルがアップロードされたら実行"""
    data = cloud_event.data
    bucket, name = data["bucket"], data["name"]
    print(f"📄 Triggered by file: gs://{bucket}/{name}")

    try:
        # Step 1. Document AI で解析
        result = process_pdf(bucket, name)
        print(f"✅ Document AI解析完了: {result.get('vendor', '不明な会社')}")

        # Step 2. 会社分類（company_master参照）
        company_info = classify_company(result.get("vendor"))

        if company_info:
            print(f"✅ 該当会社: {company_info['vendor']}")
            print(f"📘 転記先テーブル: {company_info.get('target_table', '未設定')}")
            print(f"🆔 kintone app id: {company_info.get('kintone_app_id', '不明')}")
        else:
            print(f"⚠️ 未登録の会社です。Kintoneで先に登録してください: {result.get('vendor')}")
            return  # 未登録会社は登録せず終了

        # Step 3. Kintoneへ書き込み
        try:
            post_to_kintone(result)
            print("✅ Kintoneへの登録完了")
        except Exception as e:
            print(f"❌ Kintone登録エラー: {e}")
            return

        # Step 4. JSON結果を保存
        try:
            out_uri = save_json(bucket, name, result)
            print(f"💾 JSONを保存しました: {out_uri}")
        except Exception as e:
            print(f"⚠️ JSON保存エラー: {e}")

    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        raise  # Cloud Functionsで再試行させたい場合

    print("✅ 処理完了")
import os
import re
import json
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
from google.cloud import storage, documentai
from google.api_core.client_options import ClientOptions
from vertexai.preview.generative_models import GenerativeModel
import vertexai
import functions_framework

# ==== 環境変数 ====
load_dotenv()
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION", "us")  # Document AI用
PROCESSOR_ID = os.environ.get("PROCESSOR_ID")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET")

# ==== クライアント初期化 ====
storage_client = storage.Client()
docai_client = documentai.DocumentProcessorServiceClient(
    client_options=ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
)

# ==== Utility ====
def _to_decimal(x):
    """数値文字列をDecimalに安全変換"""
    if x is None:
        return None
    try:
        s = str(x)
        s = re.sub(r"[^\d,\.]", "", s)
        if not s:
            return None
        s = s.replace(",", "")
        return Decimal(s)
    except InvalidOperation:
        return None


# ==== Geminiを使用して4項目を抽出 ====
def extract_with_gemini(text: str) -> dict:
    """
    Gemini 2.5 Flash Previewを使用して company / amount_excl_tax / amount_incl_tax / due_date を抽出。
    """
    fields = {
        "company": None,
        "tool": None,
        "department": None,
        "amount_excl_tax": None,
        "amount_incl_tax": None,
        "due_date": None
    }

    if not text or len(text) < 40:
        return fields

    try:
        # === Gemini初期化 ===
        vertexai.init(project=PROJECT_ID, location="us-central1")
        model = GenerativeModel("gemini-2.0-flash")

        # === 強化プロンプト ===
        prompt = f"""
以下は請求書のテキストです。
次の4項目を正確に抽出して、必ずJSONのみで出力してください。

抽出ルール:
- company: 「株式会社」「有限会社」で始まる発行会社名
- amount_excl_tax: 「小計」「税抜」「外税対象金額」のいずれかに対応する金額（数字とカンマのみ）
- amount_incl_tax: 「合計」「ご請求金額」「総額」「税込」に対応する最大の金額（数字とカンマのみ）
- due_date: 「支払期限」「お支払期日」「入金期日」に該当する日付（YYYY/MM/DD形式）
- 「発行日」「請求日」「検針日」などは支払期限として扱わない
- 金額は日本円表記の最大値を採用
- JSON以外の説明文は出力禁止

テキスト:
{text}

出力フォーマット:
{{
  "company": "...",
  "amount_excl_tax": "...",
  "amount_incl_tax": "...",
  "due_date": "YYYY/MM/DD"
}}
"""
        response = model.generate_content(prompt)
        raw = (response.text or "").strip()
        print("[DEBUG] Gemini raw output:", raw[:300])

        ai_fields = {}
        if raw:
            # JSON部分のみ抽出
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                try:
                    ai_fields = json.loads(m.group(0))
                except json.JSONDecodeError:
                    ai_fields = {}

        # === フォールバック（Geminiが失敗した場合） ===
        if not ai_fields:
            company = re.search(r'(?:株式|有限)会社[^\s　\n]+', text)
            amount_incl = re.search(r"(?:合計|ご請求金額)[^\d¥￥]*[¥￥]?\s*([\d,]+)", text)
            amount_excl = re.search(r"(?:小計|税抜金額)[^\d¥￥]*[¥￥]?\s*([\d,]+)", text)
            due = re.search(r"支払期限[^\d]*(\d{4})[年/.\-](\d{1,2})[月/.\-](\d{1,2})", text)

            if company:
                ai_fields["company"] = company.group(0)
            if amount_excl:
                val = _to_decimal(amount_excl.group(1))
                ai_fields["amount_excl_tax"] = f"{int(val):,}" if val else None
            if amount_incl:
                val = _to_decimal(amount_incl.group(1))
                ai_fields["amount_incl_tax"] = f"{int(val):,}" if val else None
            if due:
                y, mo, d = map(int, due.groups())
                ai_fields["due_date"] = datetime(y, mo, d).date().isoformat()

        # === 結果統合 ===
        fields.update({
            "company": ai_fields.get("company"),
            "amount_excl_tax": ai_fields.get("amount_excl_tax"),
            "amount_incl_tax": ai_fields.get("amount_incl_tax"),
            "due_date": ai_fields.get("due_date")
        })

    except Exception as e:
        print(f"[WARN] Gemini extraction failed: {e}")

    return fields


# ==== Document AI OCR処理 ====
def process_pdf(bucket_name: str, blob_name: str) -> dict:
    try:
        # --- PDFダウンロード ---
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            blob.download_to_filename(tmp.name)
            pdf_path = tmp.name

        # --- Document AI呼び出し ---
        name = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)
        with open(pdf_path, "rb") as f:
            raw_document = documentai.RawDocument(content=f.read(), mime_type="application/pdf")

        process_options = documentai.ProcessOptions(
            ocr_config=documentai.OcrConfig(
                enable_image_quality_scores=False,
                enable_symbol=False,
                premium_features=documentai.OcrConfig.PremiumFeatures(
                    enable_selection_mark_detection=False
                )
            )
        )

        request = documentai.ProcessRequest(
            name=name,
            raw_document=raw_document,
            process_options=process_options,
            skip_human_review=True
        )
        result = docai_client.process_document(request=request)
        doc = result.document

        # --- OCRテキスト取得 ---
        ocr_text = doc.text or ""
        print("[DEBUG] OCR text preview:", ocr_text[:500])

        # --- Geminiで抽出 ---
        fields = extract_with_gemini(ocr_text)
        fields["_source"] = {
            "bucket": bucket_name,
            "name": blob_name,
            "processor_id": PROCESSOR_ID,
            "location": LOCATION,
            "status": "success"
        }
        return fields

    except Exception as e:
        print(f"[ERROR] Document AI failed: {e}")
        return {
            "_source": {
                "bucket": bucket_name,
                "name": blob_name,
                "processor_id": PROCESSOR_ID,
                "location": LOCATION,
                "status": "error",
                "error_message": str(e)
            }
        }


# ==== JSON保存 ====
def save_json(to_bucket: str, source_blob_name: str, data: dict):
    try:
        base = source_blob_name.rsplit("/", 1)[-1]
        json_name = re.sub(r"\.pdf$", "", base, flags=re.I) + ".json"
        bucket = storage_client.bucket(to_bucket)
        out_blob = bucket.blob(json_name)
        out_blob.upload_from_string(
            json.dumps(data, ensure_ascii=False, indent=2),
            content_type="application/json"
        )
        print(f"Saved JSON to gs://{to_bucket}/{json_name}")
        return f"gs://{to_bucket}/{json_name}"
    except Exception as e:
        print(f"[ERROR] Failed to save JSON: {e}")
        return None


# ==== GCSトリガー ====
@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    data = cloud_event.data
    bucket = data["bucket"]
    name = data["name"]
    print(f"[DEBUG] Triggered by file: gs://{bucket}/{name}")

    try:
        result = process_pdf(bucket, name)
        target_bucket = OUTPUT_BUCKET or bucket
        out_uri = save_json(target_bucket, name, result)
        print(f"[INFO] Saved JSON to {out_uri}")
    except Exception as e:
        print(f"[FATAL] Unexpected error: {e}")

import pandas as pd
from excel_updater import update_invoice_fields

def main():
    # Excelファイル読み込み
    df = pd.read_excel("updater_test.xlsx", sheet_name="詳細")

    # Document AIなどで抽出した結果（例）
    result_data = {
        "company": "株式会社インゲージ",
        "amount_incl_tax": 75416,
        "amount_excl_tax": 68560,
        "due_date": "2025-09-30"
    }

    # Excel更新
    df = update_invoice_fields(df, result_data)

    # 保存
    df.to_excel("updater_test.xlsx", index=False)
    print("✅ Excelを更新しました。")

if __name__ == "__main__":
    main()

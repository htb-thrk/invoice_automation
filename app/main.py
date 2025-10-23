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
LOCATION = os.environ.get("LOCATION", "us")  # GeminiとForm Parser両対応
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
    Gemini Flash を使用して company / amount_excl_tax / amount_incl_tax / due_date を抽出
    """
    fields = {
        "company": None,
        "tool": None,
        "department": None,
        "amount_excl_tax": None,
        "amount_incl_tax": None,
        "due_date": None
    }

    if not text or len(text) < 50:
        return fields

    try:
        # Gemini初期化
        vertexai.init(project=PROJECT_ID, location="us-central1")
        model = GenerativeModel("gemini-1.5-flash")

        prompt = f"""
以下の請求書テキストから次の4項目を抽出して、JSON形式で出力してください。
- company: 請求書発行会社名
- amount_excl_tax: 小計または税抜金額（カンマ区切りで）
- amount_incl_tax: 合計または税込金額（カンマ区切りで）
- due_date: 支払期限やお支払期日（YYYY-MM-DD形式）

テキスト:
{text}

出力形式:
{{
  "company": "...",
  "amount_excl_tax": "...",
  "amount_incl_tax": "...",
  "due_date": "YYYY-MM-DD"
}}
"""
        response = model.generate_content(prompt)
        print("[DEBUG] Gemini raw output:", response.text[:500])

        try:
            ai_fields = json.loads(response.text)
        except json.JSONDecodeError:
            ai_fields = {}
            # フォーマットが崩れた場合、正規表現で補完
            company = re.search(r'(?:株式|有限)会社[^\s　\n]+', text)
            amount_incl = re.search(r"[¥￥]?\s*([\d,]+)\s*(?:円|税込|合計)", text)
            amount_excl = re.search(r"[¥￥]?\s*([\d,]+)\s*(?:円|税抜|小計)", text)
            due = re.search(r"(\d{4})[年/.\-](\d{1,2})[月/.\-](\d{1,2})", text)

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

        # Gemini結果を fields に統合
        fields["company"] = ai_fields.get("company")
        fields["amount_excl_tax"] = ai_fields.get("amount_excl_tax")
        fields["amount_incl_tax"] = ai_fields.get("amount_incl_tax")
        fields["due_date"] = ai_fields.get("due_date")

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

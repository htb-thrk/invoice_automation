# modules/docai_processor.py
import os
import re
import json
import tempfile
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from google.cloud import storage, documentai
from google.api_core.client_options import ClientOptions
from vertexai.preview.generative_models import GenerativeModel
import vertexai

# ロガー設定
logger = logging.getLogger(__name__)

# ==== ベンダー名正規化 ====
def normalize_vendor_name(name: str) -> str:
    """
    ベンダー名を正規化
    - 株式会社などの法人格を除去
    - OCR誤認識（印影）を修正（例: 「リンクク」→「リンク」）
    - 全角・半角スペースを除去
    """
    if not name:
        return name
    
    # 株式会社、（株）、㈱を除去
    normalized = re.sub(r"株式会社|（株）|㈱|\(株\)|有限会社", "", name)
    
    # OCR誤認識パターンを修正（印影による重複文字）
    ocr_corrections = {
        r"リンクク": "リンク",
    }
    
    for pattern, replacement in ocr_corrections.items():
        normalized = re.sub(pattern, replacement, normalized)
    
    # 全角・半角スペースを除去
    normalized = re.sub(r"\s+", "", normalized)
    
    logger.debug(f"ベンダー名正規化: '{name}' → '{normalized}'")
    return normalized.strip() if normalized else name

# ==== 共通：数値変換 ====
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
    except (InvalidOperation, ValueError):
        return None


# ==== Geminiを使用して4項目を抽出 ====
def extract_with_gemini(text: str, project_id: str) -> dict:
    """
    Gemini 2.0 Flashを使用して vendor / subtotal / total / due_date を抽出
    """
    fields = {
        "vendor": None,
        "subtotal": None,
        "total": None,
        "due_date": None,
    }

    if not text or len(text) < 40:
        logger.warning("⚠️ テキストが短すぎます")
        return fields

    try:
        # === Gemini初期化 ===
        vertexai.init(project=project_id, location="us-central1")
        model = GenerativeModel("gemini-2.0-flash")

        # === プロンプト ===
        prompt = f"""
以下は請求書のテキストです。
次の4項目を正確に抽出して、必ずJSONのみで出力してください。

抽出ルール:
- vendor: 「株式会社」「有限会社」で始まる発行会社名
- subtotal: 「小計」「税抜」「外税対象金額」のいずれかに対応する金額（数字のみ、カンマ除去）
- total: 「合計」「ご請求金額」「総額」「税込」に対応する最大の金額（数字のみ、カンマ除去）
- due_date: 「支払期限」「お支払期日」「入金期日」に該当する日付（YYYY-MM-DD形式）
- 「発行日」「請求日」「検針日」などは支払期限として扱わない
- 金額は日本円表記の最大値を採用
- JSON以外の説明文は出力禁止

テキスト:
{text[:2000]}

出力フォーマット:
{{
  "vendor": "...",
  "subtotal": 数字のみ,
  "total": 数字のみ,
  "due_date": "YYYY-MM-DD"
}}
"""
        response = model.generate_content(prompt)
        raw = (response.text or "").strip()
        logger.info(f"🤖 Gemini raw output: {raw[:300]}")

        ai_fields = {}
        if raw:
            # JSON部分のみ抽出
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                try:
                    ai_fields = json.loads(m.group(0))
                    logger.info(f"✅ Gemini parsed: {ai_fields}")
                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ JSON parse failed: {e}")
                    ai_fields = {}

        # === フォールバック（Geminiが失敗した場合） ===
        if not ai_fields or not any(ai_fields.values()):
            logger.warning("⚠️ Gemini extraction failed, using regex fallback")
            
            company = re.search(r'(?:株式|有限)会社[^\s　\n]+', text)
            amount_total = re.search(r"(?:合計|ご請求金額|総額)[^\d¥￥]*[¥￥]?\s*([\d,]+)", text)
            amount_subtotal = re.search(r"(?:小計|税抜金額)[^\d¥￥]*[¥￥]?\s*([\d,]+)", text)
            due = re.search(r"(?:支払期限|お支払期日|入金期日)[^\d]*(\d{4})[年/.\-](\d{1,2})[月/.\-](\d{1,2})", text)

            if company:
                ai_fields["vendor"] = company.group(0)
            if amount_subtotal:
                val = _to_decimal(amount_subtotal.group(1))
                ai_fields["subtotal"] = float(val) if val else None
            if amount_total:
                val = _to_decimal(amount_total.group(1))
                ai_fields["total"] = float(val) if val else None
            if due:
                y, mo, d = map(int, due.groups())
                ai_fields["due_date"] = datetime(y, mo, d).date().isoformat()

        # === 結果統合 & 正規化 ===
        vendor_raw = ai_fields.get("vendor")
        fields.update({
            "vendor": normalize_vendor_name(vendor_raw) if vendor_raw else None,
            "subtotal": float(ai_fields.get("subtotal")) if ai_fields.get("subtotal") else None,
            "total": float(ai_fields.get("total")) if ai_fields.get("total") else None,
            "due_date": ai_fields.get("due_date")
        })

        logger.info(f"🔍 Final extracted fields: {fields}")

    except Exception as e:
        logger.error(f"❌ Gemini extraction error: {e}", exc_info=True)

    return fields


# ==== PDFをDocument AIで解析 ====
def process_pdf(bucket_name: str, blob_name: str) -> dict:
    """GCSからPDFを取得してDocument AIに送信、Geminiで抽出"""
    logger.info(f"Processing PDF: gs://{bucket_name}/{blob_name}")

    try:
        # クライアント初期化
        storage_client = storage.Client()
        project_id = os.environ["GCP_PROJECT_ID"]
        location = os.environ.get("DOCAI_LOCATION", "us")
        processor_id = os.environ["DOCAI_PROCESSOR_ID"]
        
        docai_client = documentai.DocumentProcessorServiceClient(
            client_options=ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
        )

        # GCSからPDFダウンロード
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            blob.download_to_filename(tmp.name)
            pdf_path = tmp.name

        # Document AI呼び出し（OCRのみ）
        processor_name = docai_client.processor_path(project_id, location, processor_id)
        logger.info(f"🔧 Using processor: {processor_name}")
        
        with open(pdf_path, "rb") as f:
            raw_document = documentai.RawDocument(content=f.read(), mime_type="application/pdf")
        
        result = docai_client.process_document(request={"name": processor_name, "raw_document": raw_document})
        doc = result.document

        # OCRテキスト取得
        ocr_text = doc.text or ""
        logger.info(f"📄 OCR text length: {len(ocr_text)}")
        logger.info(f"📝 OCR preview: {ocr_text[:500]}")

        # Geminiで抽出
        fields = extract_with_gemini(ocr_text, project_id)
        fields["_source"] = {
            "bucket": bucket_name,
            "name": blob_name,
            "processor_id": processor_id,
            "location": location,
            "status": "success"
        }
        
        logger.info(f"✅ Extracted fields: {fields}")
        return fields

    except Exception as e:
        logger.error(f"❌ PDF processing error: {e}", exc_info=True)
        return {
            "vendor": None,
            "subtotal": None,
            "total": None,
            "due_date": None,
            "_source": {
                "bucket": bucket_name,
                "name": blob_name,
                "status": "error",
                "error_message": str(e)
            }
        }


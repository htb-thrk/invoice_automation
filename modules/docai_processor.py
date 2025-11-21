# modules/document_ai_utils.py
import os
import re
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from google.cloud import storage, documentai
from google.api_core.client_options import ClientOptions

# ==== 共通：数値変換 ====
def _to_decimal(x):
    try:
        return Decimal(str(x).replace(",", "").strip())
    except Exception:
        return None

# ==== Document AIからデータ抽出 ====
def extract_fields(doc):
    """Document AIのDocumentオブジェクトから請求書情報を抽出"""
    fields = {
        "vendor": None,
        "subtotal": None,
        "total": None,
        "due_date": None,
    }

    entities = list(doc.entities) if getattr(doc, "entities", None) else []
    
    # デバッグ: 抽出されたエンティティを表示
    print(f"📊 Document AI が抽出したエンティティ数: {len(entities)}")
    for e in entities[:10]:  # 最初の10個を表示
        print(f"  - type: {e.type_}, text: {e.mention_text or 'N/A'}")

    def best_entity(types):
        for t in types:
            for e in entities:
                if t in (e.type_ or "").lower():
                    return e
        return None

    def entity_text(e):
        if not e:
            return None
        if e.mention_text:
            return e.mention_text.strip()
        if e.text_anchor and doc.text:
            start = e.text_anchor.text_segments[0].start_index or 0
            end = e.text_anchor.text_segments[0].end_index or 0
            return doc.text[start:end].strip()
        return None

    # --- 社名
    e_company = best_entity(["supplier_name", "vendor_name", "seller_name"])
    fields["vendor"] = entity_text(e_company)

    # --- 金額
    e_subtotal = best_entity(["subtotal", "net_amount"])
    e_total = best_entity(["total", "grand_total"])
    subtotal = _to_decimal(entity_text(e_subtotal))
    total = _to_decimal(entity_text(e_total))
    fields["subtotal"] = float(subtotal) if subtotal else None
    fields["total"] = float(total) if total else None

    # --- 入金期日
    e_due = best_entity(["due_date", "payment_due_date"])
    due_raw = entity_text(e_due)
    if due_raw:
        m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", due_raw)
        if m:
            y, mo, d = map(int, m.groups())
            fields["due_date"] = datetime(y, mo, d).date().isoformat()

    print(f"🔍 抽出結果: {fields}")
    return fields


# ==== PDFをDocument AIで解析 ====
def process_pdf(bucket_name: str, blob_name: str) -> dict:
    """GCSからPDFを取得してDocument AIに送信、抽出結果を返す"""
    print(f"Processing PDF: gs://{bucket_name}/{blob_name}")

    # クライアント初期化
    storage_client = storage.Client()
    docai_client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(api_endpoint=f"{os.environ.get('LOCATION', 'us')}-documentai.googleapis.com")
    )

    # GCSからPDFダウンロード
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        blob.download_to_filename(tmp.name)
        pdf_path = tmp.name

    # Document AI呼び出し
    processor_name = docai_client.processor_path(
        os.environ["GCP_PROJECT_ID"], os.environ["DOCAI_LOCATION"], os.environ["DOCAI_PROCESSOR_ID"]
    )
    with open(pdf_path, "rb") as f:
        raw_document = documentai.RawDocument(content=f.read(), mime_type="application/pdf")
    result = docai_client.process_document(request={"name": processor_name, "raw_document": raw_document})
    doc = result.document

    fields = extract_fields(doc)
    fields["_source"] = {"bucket": bucket_name, "name": blob_name}
    print(f"✅ Extracted fields: {fields}")
    return fields

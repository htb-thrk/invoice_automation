import os
import re
import json
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv

from google.cloud import storage
from google.cloud import documentai
from google.api_core.client_options import ClientOptions
import functions_framework

# ==== 環境変数の読み込み ====
load_dotenv()
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION", "us")
PROCESSOR_ID = os.environ.get("PROCESSOR_ID")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET")

# ==== クライアント初期化 ====
storage_client = storage.Client()
docai_client = documentai.DocumentProcessorServiceClient(
    client_options=ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
)


# ==== ユーティリティ関数 ====
def _to_decimal(x):
    if x is None:
        return None
    try:
        return Decimal(str(x).replace(",", "").strip())
    except InvalidOperation:
        return None


def _best_entity(entities, type_candidates):
    """type_ の部分一致優先・最短一致"""
    for cand in type_candidates:
        for e in entities:
            if cand in (e.type_ or "").lower():
                return e
    return None


def _entity_text(doc, e):
    if not e:
        return None
    if getattr(e, "mention_text", ""):
        return e.mention_text.strip()
    if e.text_anchor and doc.text:
        start = e.text_anchor.text_segments[0].start_index or 0
        end = e.text_anchor.text_segments[0].end_index or 0
        return doc.text[start:end].strip()
    return None


def _guess_tool_name(doc):
    text = doc.text or ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    key_pat = re.compile(r"(費目|商?品名|摘要|内容|サービス名?)", re.I)
    token_pat = re.compile(r"[A-Za-z0-9\.\-_]{3,}|[ァ-ンヴー]{3,}")

    for i, ln in enumerate(lines):
        if key_pat.search(ln):
            candidates = token_pat.findall(ln)
            if i + 1 < len(lines):
                candidates += token_pat.findall(lines[i + 1])
            if candidates:
                candidates.sort(key=len, reverse=True)
                return candidates[0]
    all_cand = token_pat.findall(text)
    return max(all_cand, key=len) if all_cand else None


def _guess_department(doc):
    text = doc.text or ""
    m = re.search(r"(?:部署|部|課)\s*[:：]?\s*([^\s　/()（）【】\[\]]{2,20})", text)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"(?:ご担当)\s*([^\s　/()（）【】\[\]]{2,20})", text)
    if m2:
        return m2.group(1).strip()
    return None


def _parse_amount(text):
    if not text:
        return None
    m = re.search(r"-?\d[\d,]*\.?\d*", text)
    return _to_decimal(m.group(0)) if m else None


def extract_fields(doc):
    """Document AIの結果からフィールド抽出"""
    fields = {
        "company": None,
        "tool": None,
        "department": None,
        "amount_excl_tax": None,
        "amount_incl_tax": None,
        "tax_amount": None,
        "due_date": None
    }

    entities = list(doc.entities) if getattr(doc, "entities", None) else []

    # --- 社名
    e_company = _best_entity(entities, ["supplier_name", "vendor_name", "seller_name", "merchant_name"])
    fields["company"] = _entity_text(doc, e_company)

    # --- 金額
    e_subtotal = _best_entity(entities, ["subtotal", "net_amount", "amount_due_excluding_tax"])
    e_total = _best_entity(entities, ["total_amount", "amount_due", "grand_total", "total"])
    subtotal = _parse_amount(_entity_text(doc, e_subtotal))
    total = _parse_amount(_entity_text(doc, e_total))

    fields["amount_excl_tax"] = float(subtotal) if subtotal is not None else None
    fields["amount_incl_tax"] = float(total) if total is not None else None

    if subtotal is not None and total is not None:
        fields["tax_amount"] = float(total - subtotal)
    else:
        e_tax = _best_entity(entities, ["tax_amount", "vat", "consumption_tax"])
        tax_val = _parse_amount(_entity_text(doc, e_tax))
        fields["tax_amount"] = float(tax_val) if tax_val is not None else None

    # --- 入金期日
    e_due = _best_entity(entities, ["due_date", "payment_due_date", "payment_terms_due_date"])
    due_raw = _entity_text(doc, e_due)
    if due_raw:
        m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", due_raw)
        if m:
            try:
                y, mo, d = map(int, m.groups())
                fields["due_date"] = datetime(y, mo, d).date().isoformat()
            except ValueError:
                pass

    # --- ツール名・部署名
    fields["tool"] = _guess_tool_name(doc)
    fields["department"] = _guess_department(doc)
    return fields


# ==== メイン処理 ====
def process_pdf(bucket_name: str, blob_name: str) -> dict:
    """PDFをDocument AIで処理し、エラー時も情報を返す"""
    try:
        # (1) PDFをダウンロード
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            blob.download_to_filename(tmp.name)
            pdf_path = tmp.name

        # (2) Document AI呼び出し
        name = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)
        with open(pdf_path, "rb") as f:
            raw_document = documentai.RawDocument(content=f.read(), mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        result = docai_client.process_document(request=request)
        doc = result.document

        # (3) 結果抽出
        fields = extract_fields(doc)
        fields["_source"] = {
            "bucket": bucket_name,
            "name": blob_name,
            "processor_id": PROCESSOR_ID,
            "location": LOCATION,
            "status": "success"
        }
        return fields

    except Exception as e:
        # 例外でもJSONを返す
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


def save_json(to_bucket: str, source_blob_name: str, data: dict):
    """JSONをGCSに保存"""
    try:
        base = source_blob_name.rsplit("/", 1)[-1]
        json_name = re.sub(r"\.pdf$", "", base, flags=re.I) + ".json"
        bucket = storage_client.bucket(to_bucket)
        out_blob = bucket.blob(json_name)
        out_blob.upload_from_string(json.dumps(data, ensure_ascii=False, indent=2),
                                    content_type="application/json")
        print(f"Saved JSON to gs://{to_bucket}/{json_name}")
        return f"gs://{to_bucket}/{json_name}"
    except Exception as e:
        print(f"[ERROR] Failed to save JSON: {e}")
        return None


@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    """GCSトリガー（Gen2 Cloud Functions用）"""
    data = cloud_event.data
    bucket = data["bucket"]
    name = data["name"]

    print(f"[DEBUG] Triggered by file: gs://{bucket}/{name}")
    print(f"[DEBUG] PROJECT_ID={PROJECT_ID}, LOCATION={LOCATION}, PROCESSOR_ID={PROCESSOR_ID}, OUTPUT_BUCKET={OUTPUT_BUCKET}")

    try:
        result = process_pdf(bucket, name)
        target_bucket = OUTPUT_BUCKET or bucket
        out_uri = save_json(target_bucket, name, result)
        print(f"[INFO] Saved JSON to {out_uri}")
    except Exception as e:
        print(f"[FATAL] Unexpected error in on_file_finalized: {e}")
        # Cloud Functions では raise しても自動リトライしない設定にしてあるのでそのまま終了

import os
import re
import json
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
from google.cloud import storage, documentai
from google.api_core.client_options import ClientOptions
import functions_framework

# ==== 環境変数 ====
load_dotenv()
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION", "us")
PROCESSOR_ID = os.environ.get("PROCESSOR_ID")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET")

# ==== クライアント ====
storage_client = storage.Client()
docai_client = documentai.DocumentProcessorServiceClient(
    client_options=ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com")
)

# ==== Utility ====
def _to_decimal(x):
    if x is None:
        return None
    try:
        return Decimal(str(x).replace(",", "").strip())
    except InvalidOperation:
        return None

def _best_entity(entities, type_candidates):
    for cand in type_candidates:
        for e in entities:
            if cand in (e.type_ or "").lower():
                return e
    return None

def _entity_text(doc, e):
    """Entity から元のテキスト（日本語含む）を抽出"""
    if not e:
        return None

    text = getattr(e, "mention_text", "") or ""

    # ① mention_text に日本語が含まれていればそのまま
    if re.search(r"[ぁ-んァ-ヶ一-龥]", text):
        return text.strip()

    # ② text_anchor があれば、その範囲から原文を取得
    if e.text_anchor and doc.text:
        seg = e.text_anchor.text_segments[0]
        start = seg.start_index or 0
        end = seg.end_index or 0
        text_slice = doc.text[start:end].strip()
        if re.search(r"[ぁ-んァ-ヶ一-龥]", text_slice):
            return text_slice

    # ③ 英語しか得られなかった場合、日本語会社名候補をdoc.text全体から補完
    fulltext = doc.text or ""
    jp_company = re.findall(r'(?:株式|有限)会社[^\s　\n]+', fulltext)
    if jp_company:
        return jp_company[0]

    # ④ 最終フォールバック
    return text.strip() or None

def _parse_amount(text):
    if not text:
        return None
    m = re.search(r"-?\d[\d,]*\.?\d*", text)
    return _to_decimal(m.group(0)) if m else None

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

def _guess_company_name(doc):
    text = doc.text or ""
    candidates = re.findall(r'(?:株式|有限)会社[^\s　\n]+', text)
    ignore = ["HTBエナジー株式会社"]
    candidates = [c for c in candidates if all(ig not in c for ig in ignore)]
    return candidates[0] if candidates else None

# ==== メイン抽出 ====
def extract_fields(doc):
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

    # --- 会社名（ハイブリッド構成）---
    e_company = _best_entity(entities, ["supplier_name", "vendor_name", "seller_name", "merchant_name"])
    company = _entity_text(doc, e_company)
    if (
        not company or
        "HTBエナジー" in company or
        re.fullmatch(r"[A-Za-z0-9\s\.\-]+", company)
    ):
        company = _guess_company_name(doc)
    fields["company"] = company

    # --- 金額関連 ---
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

    # --- 入金期日（Document AI + 日本語補完）---
    e_due = _best_entity(entities, ["due_date", "payment_due_date", "payment_terms_due_date"])
    due_raw = _entity_text(doc, e_due)
    due_date = None

    # ① Document AI結果から日付抽出
    if due_raw:
        m = re.search(r"(\d{4})[/-年](\d{1,2})[/-月](\d{1,2})", due_raw)
        if m:
            try:
                y, mo, d = map(int, m.groups())
                due_date = datetime(y, mo, d).date().isoformat()
            except ValueError:
                pass

    # ② 後処理で日本語テキストから再抽出
    if not due_date:
        text = doc.text or ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        keyword_pat = re.compile(r"(支払|支払い|お支払|お支払い|入金|ご入金|御入金|まで|迄)", re.I)

        for ln in lines:
            if keyword_pat.search(ln):
                m = re.search(r"(\d{4})[年/.-](\d{1,2})[月/.-](\d{1,2})", ln)
                if not m:
                    m = re.search(r"(\d{1,2})[月/.-](\d{1,2})[日]?", ln)
                    if m:
                        y = datetime.now().year
                        mo, d = map(int, m.groups())
                        due_date = datetime(y, mo, d).date().isoformat()
                        break
                else:
                    y, mo, d = map(int, m.groups())
                    try:
                        due_date = datetime(y, mo, d).date().isoformat()
                        break
                    except ValueError:
                        pass
    fields["due_date"] = due_date

    # --- ツール名・部署名 ---
    fields["tool"] = _guess_tool_name(doc)
    fields["department"] = _guess_department(doc)

    if not isinstance(fields, dict):
        fields = {}
    return fields

# ==== PDF処理 ====
def process_pdf(bucket_name: str, blob_name: str) -> dict:
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            blob.download_to_filename(tmp.name)
            pdf_path = tmp.name

        name = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)
        with open(pdf_path, "rb") as f:
            raw_document = documentai.RawDocument(content=f.read(), mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        result = docai_client.process_document(request=request)
        doc = result.document

        fields = extract_fields(doc) or {}
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
        out_blob.upload_from_string(json.dumps(data, ensure_ascii=False, indent=2),
                                    content_type="application/json")
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

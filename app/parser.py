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
LOCATION = os.environ.get("LOCATION", "asia-northeast1")
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


# ==== OCRテキストから主要情報を抽出 ====
def extract_from_text(text: str) -> dict:
    """Form Parser の OCR テキストから主要項目を抽出"""
    fields = {
        "company": None,
        "tool": None,
        "department": None,
        "amount_excl_tax": None,
        "amount_incl_tax": None,
        "tax_amount": None,
        "due_date": None
    }

    if not text:
        return fields

    # 改行を整形
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # === 会社名 ===
    company_match = re.findall(r'(?:株式|有限)会社[^\s　\n]+', text)
    if company_match:
        # 自社名を除外
        ignore = ["HTBエナジー株式会社"]
        company_match = [c for c in company_match if all(ig not in c for ig in ignore)]
        if company_match:
            fields["company"] = company_match[0]

    # === 部署名 ===
    dept_match = re.search(r"(?:部署|部|課)\s*[:：]?\s*([^\s　/()（）【】\[\]]{2,20})", text)
    if dept_match:
        fields["department"] = dept_match.group(1).strip()
    else:
        dept_match2 = re.search(r"(?:ご担当)\s*([^\s　/()（）【】\[\]]{2,20})", text)
        if dept_match2:
            fields["department"] = dept_match2.group(1).strip()

    # === 金額（税込） ===
    incl_match = re.search(r"(合計|ご請求金額|金額[\s　]*税込[：:]?)\s*[¥￥]?\s*([\d,]+)", text)
    if incl_match:
        fields["amount_incl_tax"] = float(_to_decimal(incl_match.group(2)))

    # === 小計（税抜） ===
    excl_match = re.search(r"(小計|税抜金額)[：:\s]*[¥￥]?\s*([\d,]+)", text)
    if excl_match:
        fields["amount_excl_tax"] = float(_to_decimal(excl_match.group(2)))

    # === 消費税 ===
    tax_match = re.search(r"(消費税|税額)[：:\s]*[¥￥]?\s*([\d,]+)", text)
    if tax_match:
        fields["tax_amount"] = float(_to_decimal(tax_match.group(2)))

    # === 支払期日 / 入金期日 ===
    keyword_pat = re.compile(r"(支払|支払い|お支払|お支払い|入金|ご入金|御入金|まで|迄)", re.I)
    for ln in lines:
        if keyword_pat.search(ln):
            m = re.search(r"(\d{4})[年/.-](\d{1,2})[月/.-](\d{1,2})", ln)
            if not m:
                m = re.search(r"(\d{1,2})[月/.-](\d{1,2})[日]?", ln)
                if m:
                    y = datetime.now().year
                    mo, d = map(int, m.groups())
                    fields["due_date"] = datetime(y, mo, d).date().isoformat()
                    break
            else:
                y, mo, d = map(int, m.groups())
                try:
                    fields["due_date"] = datetime(y, mo, d).date().isoformat()
                    break
                except ValueError:
                    pass

    # === ツール名（サービス名・商品名など） ===
    key_pat = re.compile(r"(費目|商?品名|摘要|内容|サービス名?)", re.I)
    token_pat = re.compile(r"[A-Za-z0-9\.\-_]{3,}|[ァ-ンヴー]{3,}")
    for i, ln in enumerate(lines):
        if key_pat.search(ln):
            candidates = token_pat.findall(ln)
            if i + 1 < len(lines):
                candidates += token_pat.findall(lines[i + 1])
            if candidates:
                candidates.sort(key=len, reverse=True)
                fields["tool"] = candidates[0]
                break

    return fields


# ==== メイン処理 ====
def process_pdf(bucket_name: str, blob_name: str) -> dict:
    try:
        # 1. GCS から PDF をダウンロード
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            blob.download_to_filename(tmp.name)
            pdf_path = tmp.name

        # 2. Document AI 呼び出し（Form Parser）
        name = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)
        with open(pdf_path, "rb") as f:
            raw_document = documentai.RawDocument(content=f.read(), mime_type="application/pdf")
        request = documentai.ProcessRequest(name=name, raw_document=raw_document)
        result = docai_client.process_document(request=request)
        doc = result.document

        # 3. OCRテキスト確認
        ocr_text = doc.text or ""
        print("[DEBUG] OCR text preview:", ocr_text[:500])

        # 4. OCRテキストから情報抽出
        fields = extract_from_text(ocr_text)
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

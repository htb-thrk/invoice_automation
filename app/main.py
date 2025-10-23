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
from vertexai.preview.generative_models import GeterativeModel
import vertexai

def _norm(s: str) -> str:
    return re.sub(r"[ :：\u3000]", "", s.lower()) if s else s

def _clean_value(s: str) -> str:
    if not s:
        return s
    s = s.strip()
    s = re.sub(r"[ \u3000]+", " ", s)
    s = re.sub(r"[：:]\s*$", "", s)
    return s

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
        s = str(x)
        # 数字・カンマ・ピリオド以外を除去
        s = re.sub(r"[^\d,\.]", "", s)
        if not s:
            return None
        # カンマとピリオドが両方ある場合はカンマを区切り文字（削除）とみなす
        if "," in s and "." in s:
            s = s.replace(",", "")
        # カンマのみの場合は小数点でない可能性が高いので削除
        elif "," in s and "." not in s:
            s = s.replace(",", "")
        return Decimal(s)
    except InvalidOperation:
        return None


# ==== OCRテキストから主要情報を抽出 ====
def extract_from_text(text: str) -> dict:
    fields = {
        "company": None,
        "tool": None,
        "department": None,
        "amount_excl_tax": None,
        "amount_incl_tax": None,
        "due_date": None
    }

    if not text:
        return fields

    # 改行と余白を整形
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    joined_text = " ".join(lines)

    # === 会社名 ===
    company_match = re.findall(r'(?:株式|有限)会社[^\s　\n]+', text)
    if company_match:
        ignore = ["HTBエナジー株式会社"]
        company_match = [c for c in company_match if all(ig not in c for ig in ignore)]
        if company_match:
            fields["company"] = company_match[0]

    # === 合計・税込金額 ===
    incl_match = re.search(
        r"(合計|ご請求金額|請求金額|金額[\s　]*税込[：:]?|金額[：:]?|総額)[^¥￥\d]*[¥￥]?\s*([\d\s,\.]+)",
        joined_text
    )
    if incl_match:
        val = _to_decimal(incl_match.group(2))
        if val is not None:
            fields["amount_incl_tax"] = f"{int(val):,}"

    # === 小計・税抜金額 ===
    excl_match = re.search(
        r"(小計|税抜金額|税抜き金額|外税対象金額)[^¥￥\d]*[¥￥]?\s*([\d\s,\.]+)",
        joined_text
    )
    if excl_match:
        val = _to_decimal(excl_match.group(2))
        if val is not None:
            fields["amount_excl_tax"] = f"{int(val):,}"

    # === 支払期日 ===
    keyword_pat = re.compile(
        r"(支払期限|支払い期限|お支払期限|お支払い期限|入金期日|ご入金日|御入金日|支払|支払い|お支払|お支払い|入金|ご入金|御入金|まで|迄)",
        re.I
    )
    date_pat = re.compile(r"(\d{4})[年/.\-](\d{1,2})[月/.\-](\d{1,2})")

    for i, ln in enumerate(lines):
        if keyword_pat.search(ln):
            # 行内に日付があるか
            m = date_pat.search(ln)
            if not m and i + 1 < len(lines):
                # 次の行にも日付があるか確認
                m = date_pat.search(lines[i + 1])
            if not m and i + 2 < len(lines):
                # さらに次の行も確認（表形式対応）
                m = date_pat.search(lines[i + 2])
            if m:
                try:
                    y, mo, d = map(int, m.groups())
                    fields["due_date"] = datetime(y, mo, d).date().isoformat()
                    break
                except ValueError:
                    continue

    return fields

# ==== メイン処理 ====   
def process_pdf(bucket_name: str, blob_name: str) -> dict:
    try:
        # === (1) PDFをGCSからダウンロード ===
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            blob.download_to_filename(tmp.name)
            pdf_path = tmp.name

        # === (2) Document AIでOCR処理 ===
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
        result = docai_client.process_document(request=requestimport os
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
    """カンマやピリオドを安全に処理してDecimal化"""
    if x is None:
        return None
    try:
        s = str(x)
        # 数字・カンマ・ピリオド以外を除去
        s = re.sub(r"[^\d,\.]", "", s)
        if not s:
            return None
        # カンマとピリオドを適切に扱う
        if "," in s and "." in s:
            s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", "")
        return Decimal(s)
    except InvalidOperation:
        return None


# ==== OCRテキストから主要情報を抽出 ====
def extract_from_text(text: str) -> dict:
    """
    OCRテキストから主要4項目（会社名・金額（税抜/税込）・支払期日）を抽出。
    tool / department は構造維持（破壊しない）。
    """
    fields = {
        "company": None,
        "tool": None,
        "department": None,
        "amount_excl_tax": None,
        "amount_incl_tax": None,
        "due_date": None
    }

    if not text:
        return fields

    # ===== 共通整形 =====
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    joined = " ".join(lines)

    # ===== 会社名 =====
    match = re.findall(r'(?:株式|有限)会社[^\s　\n]+', text)
    if match:
        ignore = ["HTBエナジー株式会社"]
        names = [c for c in match if all(ig not in c for ig in ignore)]
        if names:
            fields["company"] = names[0]

    # ===== 税込金額（合計・ご請求金額など） =====
    incl_match = re.search(
        r"(?:合計|総額|ご請求金額|請求金額|金額[\s　]*税込)[^¥￥\d]*[¥￥]?\s*([\d,\.]+)",
        joined
    )
    if incl_match:
        val = _to_decimal(incl_match.group(1))
        if val is not None:
            fields["amount_incl_tax"] = f"{int(val):,}"

    # ===== 税抜金額（小計・税抜き金額など） =====
    excl_match = re.search(
        r"(?:小計|税抜金額|税抜き金額|外税対象金額)[^¥￥\d]*[¥￥]?\s*([\d,\.]+)",
        joined
    )
    if excl_match:
        val = _to_decimal(excl_match.group(1))
        if val is not None:
            fields["amount_excl_tax"] = f"{int(val):,}"

    # ===== 支払期日 =====
    date_pat = re.compile(r"(\d{4})[年/.\-](\d{1,2})[月/.\-](\d{1,2})")
    keyword_pat = re.compile(
        r"(支払期限|支払い期限|お支払期限|お支払い期限|入金期日|ご入金日|御入金日|支払|支払い|お支払|お支払い|入金|ご入金|御入金|まで|迄)",
        re.I
    )

    for i, line in enumerate(lines):
        if keyword_pat.search(line):
            # 同じ行 or 次の2行以内に日付を探索（表形式にも対応）
            for j in range(3):
                if i + j < len(lines):
                    m = date_pat.search(lines[i + j])
                    if m:
                        try:
                            y, mo, d = map(int, m.groups())
                            fields["due_date"] = datetime(y, mo, d).date().isoformat()
                            break
                        except ValueError:
                            continue
            if fields["due_date"]:
                break

    return fields


# ==== メイン処理 ====
def process_pdf(bucket_name: str, blob_name: str) -> dict:
    try:
        # === 1. PDFをダウンロード ===
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            blob.download_to_filename(tmp.name)
            pdf_path = tmp.name

        # === 2. Document AI呼び出し ===
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

        # === 3. OCRテキスト取得 ===
        ocr_text = doc.text or ""
        print("[DEBUG] OCR text preview:", ocr_text[:500])

        # === 4. 情報抽出 ===
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
        # 金額フィールドを3桁カンマ区切りで整形
        for k in ["amount_excl_tax", "amount_incl_tax"]:
            v = data.get(k)
            if isinstance(v, (int, float, Decimal)):
                data[k] = f"{int(v):,}"

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

        doc = result.document

        # === (3) OCRテキスト取得 ===
        ocr_text = doc.text or ""
        print("[DEBUG] OCR text preview:", ocr_text[:500])

        # === (4) Gemini Flashによる自然言語抽出 ===
        try:
            vertexai.init(project=PROJECT_ID, location=LOCATION)
            model = GenerativeModel("gemini-1.5-flash")

            prompt = f"""
以下の請求書テキストから「支払期限」と「御請求金額（税込）」を抽出してください。
結果は次の形式のJSONで出力してください。
{{
  "due_date": "YYYY-MM-DD",
  "amount_incl_tax": "金額（カンマ区切り）"
}}
テキスト：
{ocr_text}
"""
            response = model.generate_content(prompt)
            gemini_data = response.text.strip()
            print("[DEBUG] Gemini raw output:", gemini_data)

            # JSONとして扱えるようにパース
            try:
                ai_fields = json.loads(gemini_data)
            except json.JSONDecodeError:
                # Geminiがフォーマットを少し崩した場合の再整形
                ai_fields = {}
                date_match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", gemini_data)
                amount_match = re.search(r"([\d,]+)", gemini_data)
                if date_match:
                    y, mo, d = map(int, date_match.groups())
                    ai_fields["due_date"] = datetime(y, mo, d).date().isoformat()
                if amount_match:
                    ai_fields["amount_incl_tax"] = amount_match.group(1)
        except Exception as gemini_error:
            print(f"[WARN] Gemini Flash failed: {gemini_error}")
            ai_fields = {}

        # === (5) 最終出力を統合 ===
        fields = {
            "company": None,
            "tool": None,
            "department": None,
            "amount_excl_tax": None,
            "amount_incl_tax": ai_fields.get("amount_incl_tax"),
            "due_date": ai_fields.get("due_date")
        }

        fields["_source"] = {
            "bucket": bucket_name,
            "name": blob_name,
            "processor_id": PROCESSOR_ID,
            "location": LOCATION,
            "status": "success"
        }
        return fields


# ==== JSON保存 ====
def save_json(to_bucket: str, source_blob_name: str, data: dict):
    try:
        # --- 金額フィールドを3桁カンマ区切りで整形 ---
        for k in ["amount_excl_tax", "amount_incl_tax"]:
            v = data.get(k)
            if isinstance(v, (int, float, Decimal)):
                data[k] = f"{int(v):,}"

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

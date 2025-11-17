import json
import re
import requests
import os
from typing import Any, Dict

# --- 設定 ---
KINTONE_DOMAIN = os.environ["KINTONE_DOMAIN"]
APP_ID = os.environ["KINTONE_APP_ID"]
API_TOKEN = os.environ["KINTONE_API_TOKEN"]

# ==========================
#  Utility
# ==========================

def normalize_vendor(name: str) -> str:
    """'株式会社' の有無を無視し、空白を除去"""
    if not name:
        return ""
    name = re.sub(r"株式会社|（株）|㈱", "", name)
    name = re.sub(r"\s+", "", name)
    return name


def load_master() -> list:
    with open(MASTER_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def find_vendor_exact(vendor_name: str, master: list) -> dict | None:
    """vendor を正規化して完全一致で照合"""
    normalized = normalize_vendor(vendor_name)
    for rec in master:
        if normalize_vendor(rec["vendor"]) == normalized:
            return rec
    return None


# ==========================
#  Validation
# ==========================

def validate_docai_result(docai_result: Dict[str, Any]) -> None:
    """
    必須フィールドのバリデーション。
    欠損または非数値・無効な日付の場合は例外を送出。
    """
    required = ["vendor", "subtotal", "total", "due_date"]
    missing = [k for k in required if not docai_result.get(k)]
    if missing:
        raise ValueError(f"Document AI 結果に必須値が欠けています: {', '.join(missing)}")

    # 数値フィールドの型チェック
    for key in ["subtotal", "total"]:
        val = docai_result.get(key)
        try:
            float(val)
        except (TypeError, ValueError):
            raise ValueError(f"{key} の値が数値ではありません: {val}")

    # 日付形式の簡易チェック（YYYY-MM-DD）
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", docai_result.get("due_date", "")):
        raise ValueError(f"due_date の形式が不正です: {docai_result.get('due_date')}")


# ==========================
#  Kintone操作
# ==========================

def add_kintone_record(record: Dict[str, Any]) -> None:
    """Kintoneにレコードを追加"""
    url = f"{KINTONE_DOMAIN}/k/v1/record.json"
    headers = {
        "X-Cybozu-API-Token": API_TOKEN,
        "Content-Type": "application/json"
    }

    resp = requests.post(url, headers=headers, json=record)
    if resp.status_code == 200:
        print(f"✅ Kintone追加成功: {record['record']['vendor']['value']}")
    else:
        raise RuntimeError(f"❌ Kintone追加失敗: {resp.status_code} {resp.text}")


# ==========================
#  Main Function
# ==========================

def push_from_docai(docai_result: Dict[str, Any]) -> None:
    """Document AIの抽出結果をKintoneに追加"""
    # Step 1: バリデーション
    try:
        validate_docai_result(docai_result)
    except ValueError as e:
        print(f"❌ 入力データ不正: {e}")
        raise

    # Step 3: Kintoneへ追加
    ##FIXME: レコードの追加に失敗した場合のリトライやエラーハンドリングを強化する
    record = {
        "app": APP_ID,
        "record": {
            "vendor": {"value": hit["vendor"]},
            "subtotal": {"value": str(docai_result["subtotal"])},
            "total": {"value": str(docai_result["total"])},
            "due_date": {"value": docai_result["due_date"]},
        }
    }

    add_kintone_record(record)
    print(f"✅ レコード追加完了: {hit['vendor']}")
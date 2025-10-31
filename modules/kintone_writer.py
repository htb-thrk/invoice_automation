import os
import requests

def post_to_kintone(fields: dict) -> bool:
    """抽出結果を kintone に書き込む"""
    try:
        domain = os.environ["KINTONE_DOMAIN"]
        app_id = os.environ["KINTONE_APP_ID"]
        token = os.environ["KINTONE_API_TOKEN"]

        url = f"https://{domain}/k/v1/record.json"
        headers = {
            "X-Cybozu-API-Token": token,
            "Content-Type": "application/json"
        }

        # --- 数値フィールドは float 変換＋None対策 ---
        def safe_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0  # ← DocumentAIが値を取れなかった場合は0円として送る

        amount_excl_tax = safe_float(fields.get("amount_excl_tax"))
        amount_incl_tax = safe_float(fields.get("amount_incl_tax"))
        due_date = fields.get("due_date") or ""  # None対策

        record = {
            "amount_excl_tax": {"value": amount_excl_tax},
            "amount_incl_tax": {"value": amount_incl_tax},
            "progress": {"value": "承認"},
            "due_date": {"value": due_date},
        }

        payload = {"app": app_id, "record": record}
        r = requests.post(url, headers=headers, json=payload)
        r.raise_for_status()
        print("✅ Kintone登録:", r.json())
        return True

    except requests.exceptions.HTTPError as e:
        print("[ERROR] Kintone書き込み失敗（HTTPError）:")
        print("ステータス:", e.response.status_code)
        print("レスポンス本文:", e.response.text)
        return False
    except Exception as e:
        print(f"[ERROR] Kintone書き込み失敗: {e}")
        return False

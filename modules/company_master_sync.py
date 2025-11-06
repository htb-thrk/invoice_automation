import os
import requests
import json
from datetime import datetime

def fetch_kintone_master():
    """
    Kintoneの「会社マスタ」アプリからレコードを取得して、
    company_master.json に自動反映する
    """
    domain = os.environ["KINTONE_DOMAIN"]
    app_id = os.environ["KINTONE_MASTER_APP_ID"]   # ← 会社マスタ管理アプリID
    token = os.environ["KINTONE_MASTER_API_TOKEN"] # ← そのアプリのAPIトークン

    url = f"https://{domain}/k/v1/records.json"
    headers = {
        "X-Cybozu-API-Token": token,
        "Content-Type": "application/json"
    }

    params = {
        "app": app_id,
        "fields": ["社名", "ツール名／業務内容", "利用部署", "n月分"],
        "totalCount": "true"
    }

    res = requests.get(url, headers=headers, params=params)
    res.raise_for_status()
    data = res.json()

    records = []
    for rec in data.get("records", []):
        record = {
            "社名": rec.get("社名", {}).get("value"),
            "ツール名／業務内容": rec.get("ツール名／業務内容", {}).get("value"),
            "利用部署": rec.get("利用部署", {}).get("value"),
            "n月分": rec.get("n月分", {}).get("value")
        }
        records.append(record)

    # 保存
    os.makedirs("company_master", exist_ok=True)
    output_path = f"company_master/company_master_{datetime.now().year}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"✅ company_master.json を更新しました: {output_path}")
    return output_path

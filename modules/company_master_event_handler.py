import os
import json
import re
from flask import Request

KINTONE_DOMAIN = os.environ["KINTONE_DOMAIN"]
APP_ID = os.environ["KINTONE_APP_ID"]
API_TOKEN = os.environ["KINTONE_API_TOKEN"]

MASTER_PATH = os.environ.get(
    "MASTER_PATH",
    os.path.join(os.path.dirname(__file__), "company_master_2025.json")
)

def load_master():
    try:
        with open(MASTER_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_master(data):
    os.makedirs(os.path.dirname(MASTER_PATH), exist_ok=True)
    with open(MASTER_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def sync_event(event_body: dict):
    master = load_master()
    record = event_body["record"]
    operation = event_body["type"]

    def match(rec):
        return rec["vendor"] == record["vendor"]["value"]

    if operation == "ADD_RECORD":
        entry = {
            "vendor": record["vendor"]["value"],
            "tool": record["tool"]["value"],
        }
        master.append(entry)
        print(f"🟢 追加: {entry['vendor']}")
    elif operation == "EDIT_RECORD":
        for i, rec in enumerate(master):
            if match(rec):
                master[i]["tool"] = record["tool"]["value"]
                print(f"🟡 更新: {rec['vendor']}")
                break
    elif operation == "DELETE_RECORD":
        master = [rec for rec in master if not match(rec)]
        print(f"🔴 削除: {record['vendor']['value']}")

    save_master(master)
    print("✅ company_master_2025.json を更新しました")

def sync_company_master_event(request: Request):
    try:
        event = request.get_json(silent=True)
        if not event:
            return ("Invalid JSON body", 400)
        sync_event(event)
        return ("OK", 200)
    except Exception as e:
        print(f"❌ エラー: {e}")
        return (f"Error: {e}", 500)

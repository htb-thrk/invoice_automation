import os
import json
import requests
from datetime import datetime

MASTER_PATH = "company_master/company_master_latest.json"

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

def sync_event(event_body):
    """Webhookイベントの内容を反映する"""
    master = load_master()

    record = event_body["record"]
    operation = event_body["type"]  # 'ADD_RECORD', 'EDIT_RECORD', 'DELETE_RECORD'

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
                master[i].update({
                    "tool": record["tool"]["value"],
                })
                print(f"🟡 更新: {rec['vendor']}")
                break

    elif operation == "DELETE_RECORD":
        master = [rec for rec in master if not match(rec)]
        print(f"🔴 削除: {record['vendor']['value']}")

    save_master(master)
    print("✅ company_master.json を更新しました")

# Cloud Functionsエントリポイント
def sync_company_master_event(request):
    event = request.get_json(silent=True)
    sync_event(event)
    return ("OK", 200)

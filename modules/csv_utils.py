# modules/csv_utils.py
import csv
import tempfile
from datetime import datetime
from google.cloud import storage

def save_daily_csv(data: dict, output_bucket: str):
    """
    CSVファイルを出力バケットに保存
    （MVP版：フォルダなし・バケット直下）
    """
    header = [
        "ベンダー",
        "ツール名/業務内容",
        "利用部署",
        "小計（税抜）",
        "合計（税込）",
        "進捗",
        "入金期日"
    ]
    today = datetime.now().strftime("%Y%m%d")
    filename = f"Billing_Tracking_{today}.csv"

    # 行データ整形
    row = [
        data.get("company", ""),
        data.get("tool", ""),
        data.get("department", ""),
        f"{int(data['amount_excl_tax']):,}" if data.get("amount_excl_tax") else "",
        f"{int(data['amount_incl_tax']):,}" if data.get("amount_incl_tax") else "",
        "承認済",
        datetime.strptime(data["due_date"], "%Y-%m-%d").strftime("%Y/%m/%d")
        if data.get("due_date") else "",
    ]

    # CSVファイル作成→アップロード
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".csv", mode="w", encoding="utf-8-sig", newline=""
        ) as tmp:
            writer = csv.writer(tmp)
            writer.writerow(header)
            writer.writerow(row)
            tmp.flush()

            # GCSへアップロード
            storage_client = storage.Client()
            bucket = storage_client.bucket(output_bucket)
            blob = bucket.blob(filename)
            blob.upload_from_filename(tmp.name, content_type="text/csv")
            print(f"✅ Uploaded CSV: gs://{output_bucket}/{filename}", flush=True)

    except Exception as e:
    import traceback
    print(f"[ERROR] CSV upload failed: {e}", flush=True)
    print(traceback.format_exc(), flush=True)


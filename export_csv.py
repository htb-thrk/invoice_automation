import csv
import json
from datetime import datetime

def export_billing_csv(json_data, output_path="billing_tracking.csv"):
    """
    抽出済みJSONデータからGoogleスプレッドシート形式のCSVを生成
    """

    # 1️⃣ JSONデータを読み込み（dict型）
    if isinstance(json_data, str):
        with open(json_data, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json_data

    # 2️⃣ 出力カラムを定義（Billing Tracking構成）
    header = [
        "ベンダー",
        "ツール名/業務内容",
        "利用部署",
        "小計（税抜）",
        "合計（税込）",
        "進捗",
        "入金期日",
    ]

    # 3️⃣ JSONから該当データを抽出してCSV用に整形
    # Document AI抽出結果を想定
    row = [
        data.get("company", ""),
        data.get("tool", ""),
        data.get("department", ""),
        f"{int(data['amount_excl_tax']):,}" if data.get("amount_excl_tax") else "",
        f"{int(data['amount_incl_tax']):,}" if data.get("amount_incl_tax") else "",
        "承認済",  # デフォルト値または status を後で追加
        datetime.strptime(data["due_date"], "%Y-%m-%d").strftime("%Y/%m/%d") if data.get("due_date") else "",
    ]

    # 4️⃣ CSVとして書き出し（UTF-8-sig = Excel互換）
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerow(row)

    print(f"✅ CSV書き出し完了: {output_path}")


# === テスト実行用 ===
if __name__ == "__main__":
    # Document AI 抽出済み JSON 例
    data = {
        "company": "株式会社AI Shift",
        "tool": "AI messenger",
        "department": "コンタクト",
        "amount_excl_tax": 440000,
        "amount_incl_tax": 440000,
        "due_date": "2025-09-30"
    }
    export_billing_csv(data, "2025_Billing_Tracking.csv")

rows = []
for json_file in json_files:
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    rows.append([
        data.get("company", ""),
        data.get("tool", ""),
        data.get("department", ""),
        f"{int(data['amount_excl_tax']):,}" if data.get("amount_excl_tax") else "",
        f"{int(data['amount_incl_tax']):,}" if data.get("amount_incl_tax") else "",
        "承認済",
        datetime.strptime(data["due_date"], "%Y-%m-%d").strftime("%Y/%m/%d") if data.get("due_date") else "",
    ])

with open("Billing_Tracking_まとめ.csv", "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(rows)

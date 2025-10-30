import glob
import csv
import json
from datetime import datetime
from pathlib import Path

def export_billing_csv(json_data, output_dir):
    with open(json_data, "r", encoding="utf-8") as f:
        data = json.load(f)

    # === スプレッドシートと同じ列構成 ===
    header = ["ベンダー", "ツール名/業務内容", "利用部署", "小計（税抜）", "合計（税込）", "進捗", "入金期日"]

    def format_yen(value):
        """カンマ区切り＋¥付きで出力"""
        if not value:
            return ""
        try:
            val = int(str(value).replace(",", ""))
            return f"¥{val:,}"
        except ValueError:
            return str(value)

    # === 行データ ===
    row = [
        data.get("company", ""),
        data.get("tool", ""),
        data.get("department", ""),
        format_yen(data.get("amount_excl_tax")),
        format_yen(data.get("amount_incl_tax")),
        "承認済",
        datetime.strptime(data["due_date"], "%Y-%m-%d").strftime("%Y/%m/%d") if data.get("due_date") else "",
    ]

    # === ダウンロードフォルダ出力 ===
    output_path = output_dir / f"{Path(json_data).stem}.csv"
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerow(row)

    print(f"✅ CSV書き出し完了: {output_path}")

if __name__ == "__main__":
    download_dir = Path.home() / "Downloads"
    download_dir.mkdir(exist_ok=True)

    for json_file in glob.glob("*.json"):
        export_billing_csv(json_file, download_dir)

    print(f"\n📁 出力先: {download_dir}")

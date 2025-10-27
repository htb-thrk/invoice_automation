# local/export_csv.py
from modules.csv_utils import save_daily_csv
import json

with open("local/json_samples/sample_invoice.json", "r", encoding="utf-8") as f:
    data = json.load(f)

save_daily_csv(data, "local/output")
print("✅ ローカルCSV出力完了")

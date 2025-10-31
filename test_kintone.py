# test_kintone.py
import os
from dotenv import load_dotenv
from modules.kintone_writer import post_to_kintone

import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from kintone_writer import post_to_kintone


# .env の内容をロード
load_dotenv()

# テスト用のダミーデータ
fields = {
    "amount_excl_tax": 68560,
    "amount_incl_tax": 75416,
    "due_date": "2025-09-30"
}

# kintone に書き込み
result = post_to_kintone(fields)
print("書き込み結果:", result)

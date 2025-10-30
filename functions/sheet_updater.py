import os
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()

SHEET_ID = os.getenv("SHEET_ID")
SERVICE_ACCOUNT_PATH = os.getenv("SERVICE_ACCOUNT_PATH")

def update_invoice_fields(df, result_data):
    """請求書データを空行に追記"""
    cols = ["社名", "金額（税込み）", "金額（税抜）", "入金期日"]

    empty_idx = df[df.isna().all(axis=1) | (df.astype(str).apply(lambda x: x.str.strip() == "")).all(axis=1)].index
    row = empty_idx[0] if len(empty_idx) else len(df)

    for c, v in zip(cols, [
        result_data.get("company"),
        result_data.get("amount_incl_tax"),
        result_data.get("amount_excl_tax"),
        result_data.get("due_date")
    ]):
        df.at[row, c] = v

    return df

def write_to_sheet(result_data):
    """Google Sheets に書き込み"""
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_PATH, scope)
    client = gspread.authorize(creds)

    sheet = client.open_by_key(SHEET_ID).worksheet("Billing Tracking")
    df = pd.DataFrame(sheet.get_all_records())

    df = update_invoice_fields(df, result_data)
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

    print("✅ Google Sheet 更新完了")

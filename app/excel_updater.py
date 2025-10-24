import pandas as pd

def update_invoice_fields(df, result_data):
    """請求書データを空行に追記（既存データは上書きしない）"""
    cols = ["社名", "金額（税込み）", "金額（税抜）", "入金期日"]

    # 空行を探す（すべてNaN or 空文字）
    empty_idx = df[df.isna().all(axis=1) | (df.astype(str).apply(lambda x: x.str.strip() == "")).all(axis=1)].index
    if len(empty_idx) == 0:
        df.loc[len(df)] = pd.Series(dtype="object")
        row = len(df) - 1
    else:
        row = empty_idx[0]

    for c, v in zip(cols, [
        result_data.get("company"),
        result_data.get("amount_incl_tax"),
        result_data.get("amount_excl_tax"),
        result_data.get("due_date")
    ]):
        if pd.isna(df.at[row, c]) or str(df.at[row, c]).strip() == "":
            df.at[row, c] = v

    return df

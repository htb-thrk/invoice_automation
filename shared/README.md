# 共有設定とユーティリティ

このディレクトリには、Web AppとCloud Functionの両方で使用される共有リソースを配置します。

## 📁 内容

- `company_master_2025.json` - 会社マスターデータ
- `config/` - 共通設定ファイル
- `utils/` - 共通ユーティリティ関数（将来用）

## 使用方法

各アプリケーションから相対パスで参照:

```python
# function/main.py
import os
import json

MASTER_PATH = os.path.join(
    os.path.dirname(__file__), 
    "..", 
    "shared", 
    "company_master_2025.json"
)
```

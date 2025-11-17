"""
Kintone API クライアント
"""
import requests
from typing import Dict, Any, Optional


class KintoneClient:
    """Kintone API クライアント"""
    
    def __init__(self, domain: str, app_id: str, api_token: str):
        """
        初期化
        
        Args:
            domain: kintone ドメイン (例: https://example.cybozu.com)
            app_id: アプリ ID
            api_token: API トークン
        """
        self.domain = domain.rstrip('/')
        self.app_id = app_id
        self.api_token = api_token
        
        self.headers = {
            "X-Cybozu-API-Token": api_token,
            "Content-Type": "application/json"
        }
    
    def create_record(self, data: Dict[str, Any]) -> int:
        """
        レコードを作成
        
        Args:
            data: レコードデータ
            
        Returns:
            作成されたレコードID
        """
        url = f"{self.domain}/k/v1/record.json"
        
        # フィールドマッピング
        payload = {
            "app": self.app_id,
            "record": {
                "vendor": {"value": data.get("vendor") or ""},
                "subtotal": {"value": str(data.get("subtotal") or "")},
                "total": {"value": str(data.get("total") or "")},
                "due_date": {"value": data.get("due_date") or ""}
            }
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        return result.get("id")
    
    def update_record(self, record_id: int, data: Dict[str, Any]) -> None:
        """
        レコードを更新
        
        Args:
            record_id: レコードID
            data: 更新データ
        """
        url = f"{self.domain}/k/v1/record.json"
        
        payload = {
            "app": self.app_id,
            "id": record_id,
            "record": {
                "vendor": {"value": data.get("vendor") or ""},
                "subtotal": {"value": str(data.get("subtotal") or "")},
                "total": {"value": str(data.get("total") or "")},
                "due_date": {"value": data.get("due_date") or ""}
            }
        }
        
        response = requests.put(url, headers=self.headers, json=payload)
        response.raise_for_status()
    
    def get_record(self, record_id: int) -> Dict[str, Any]:
        """
        レコードを取得
        
        Args:
            record_id: レコードID
            
        Returns:
            レコードデータ
        """
        url = f"{self.domain}/k/v1/record.json"
        params = {
            "app": self.app_id,
            "id": record_id
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        return response.json().get("record", {})
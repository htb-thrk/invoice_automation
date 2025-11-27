"""
Kintone API クライアント（完全版）
- エラーハンドリング強化
- バリデーション統一
- 環境変数対応
- ロギング統合
"""
import os
import re
import json
import requests
import logging
from typing import Dict, Any, Optional, List
from decimal import Decimal, InvalidOperation
from datetime import datetime

# ロガー設定
logger = logging.getLogger(__name__)


# ============================================================
# カスタム例外
# ============================================================

class KintoneValidationError(Exception):
    """
    Kintone バリデーションエラー
    データ不正（リトライ不可）
    """
    pass


class KintoneAPIError(Exception):
    """
    Kintone API エラー
    通信エラーなど（リトライ可能）
    """
    pass


# ============================================================
# バリデーション関数
# ============================================================

def validate_amount(value: Any, field_name: str = "金額") -> Optional[float]:
    """
    金額を検証してfloatに変換
    """
    if value is None or value == "":
        return None
    
    try:
        # Decimal経由で精度を保つ
        amount = float(Decimal(str(value)))
        
        # 負の値チェック
        if amount < 0:
            raise ValueError(f"{field_name}が負の値です: {amount}")
        
        logger.debug(f"{field_name}検証成功: {amount}")
        return amount
        
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"{field_name}の形式が不正です: {value} ({str(e)})")


def validate_date(date_str: str) -> str:
    """
    日付形式を検証（YYYY-MM-DD）
    """
    if not date_str:
        return ""
    
    # YYYY-MM-DD 形式チェック
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValueError(
            f"日付形式が不正です（YYYY-MM-DD形式である必要があります）: {date_str}"
        )
    
    # 日付の妥当性チェック
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        logger.debug(f"日付検証成功: {date_str}")
    except ValueError as e:
        raise ValueError(f"日付が不正です: {date_str} ({str(e)})")
    
    return date_str


# ============================================================
# Kintone クライアント
# ============================================================

class KintoneClient:
    """
    Kintone API クライアント（エラーハンドリング強化版）
    
    環境変数:
        KINTONE_DOMAIN: kintone ドメイン (例: https://example.cybozu.com)
        KINTONE_APP_ID: アプリ ID
        KINTONE_API_TOKEN: API トークン
    
    Examples:
        # 環境変数から自動取得
        >>> client = KintoneClient()
        
        # 明示的に指定
        >>> client = KintoneClient(
        ...     domain="https://example.cybozu.com",
        ...     app_id="123",
        ...     api_token="your-token"
        ... )
    """
    
    def __init__(
        self,
        domain: Optional[str] = None,
        app_id: Optional[str] = None,
        api_token: Optional[str] = None
    ):
        """
        初期化（環境変数対応）
        
        Args:
            domain: kintone ドメイン (省略時は環境変数 KINTONE_DOMAIN から取得)
            app_id: アプリ ID (省略時は環境変数 KINTONE_APP_ID から取得)
            api_token: API トークン (省略時は環境変数 KINTONE_API_TOKEN から取得)
            
        Raises:
            ValueError: 必須パラメータが不足している場合
        """
        # 環境変数から取得（引数が指定されていない場合）
        self.domain = (domain or os.environ.get("KINTONE_DOMAIN", "")).rstrip('/')
        self.app_id = app_id or os.environ.get("KINTONE_APP_ID")
        self.api_token = api_token or os.environ.get("KINTONE_API_TOKEN")
        
        # デバッグ: 環境変数の読み込み状況を確認
        logger.debug(f"環境変数読み込み: KINTONE_DOMAIN={self.domain}")
        logger.debug(f"環境変数読み込み: KINTONE_APP_ID={self.app_id}")
        logger.debug(f"環境変数読み込み: KINTONE_API_TOKEN={'*' * (len(self.api_token) if self.api_token else 0)}文字")
        
        if not all([self.domain, self.app_id, self.api_token]):
            missing = []
            if not self.domain: missing.append("KINTONE_DOMAIN")
            if not self.app_id: missing.append("KINTONE_APP_ID")
            if not self.api_token: missing.append("KINTONE_API_TOKEN")
            raise ValueError(
                f"以下の環境変数が設定されていません: {', '.join(missing)}"
            )
        
        self.headers = {
            "X-Cybozu-API-Token": self.api_token,
            "Content-Type": "application/json"
        }
        
        logger.info(
            f"KintoneClient初期化: domain={self.domain}, app_id={self.app_id}, token_length={len(self.api_token)}"
        )
    
    def validate_record_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        レコードデータを検証
        
        Args:
            data: レコードデータ
            
        Returns:
            検証済みのレコードデータ
            
        Raises:
            KintoneValidationError: バリデーションエラー
        """
        errors = []
        validated = {}
        
        try:
            # ベンダー名の検証（必須、正規化はPDF processor側で完了済み）
            vendor = data.get("vendor")
            if not vendor:
                errors.append("ベンダー名が指定されていません")
            else:
                validated["vendor"] = vendor
            
            # 小計の検証（任意）
            try:
                validated["subtotal"] = validate_amount(
                    data.get("subtotal"),
                    "小計"
                )
            except ValueError as e:
                errors.append(str(e))
            
            # 合計の検証（任意）
            try:
                validated["total"] = validate_amount(
                    data.get("total"),
                    "合計"
                )
            except ValueError as e:
                errors.append(str(e))
            
            # 支払期日の検証（任意）
            try:
                due_date = data.get("due_date")
                validated["due_date"] = validate_date(due_date) if due_date else ""
            except ValueError as e:
                errors.append(str(e))
            
            # エラーがあれば例外を発生
            if errors:
                error_message = (
                    f"バリデーションエラー（{len(errors)}件）:\n" + 
                    "\n".join(f"  - {err}" for err in errors)
                )
                logger.error(error_message)
                raise KintoneValidationError(error_message)
            
            logger.debug(f"バリデーション成功: {validated}")
            return validated
            
        except Exception as e:
            if isinstance(e, KintoneValidationError):
                raise
            error_message = f"予期しないバリデーションエラー: {str(e)}"
            logger.error(error_message)
            raise KintoneValidationError(error_message)
    
    def create_record(self, data: Dict[str, Any]) -> int:
        """
        レコードを作成（バリデーション付き）
        
        Args:
            data: レコードデータ
            
        Returns:
            作成されたレコードID
            
        Raises:
            KintoneValidationError: バリデーションエラー
            KintoneAPIError: API呼び出しエラー
        """
        # 1. データ検証
        validated_data = self.validate_record_data(data)
        
        # 2. Kintone API用のペイロード作成
        url = f"{self.domain}/k/v1/record.json"
        
        # レコード構築（Noneの場合はフィールドを含めない）
        record = {
            "vendor": {"value": validated_data.get("vendor", "")}
        }
        
        # 数値フィールドはNoneの場合は含めない（空文字列を送るとエラーになる）
        if validated_data.get("subtotal") is not None:
            record["subtotal"] = {"value": str(validated_data["subtotal"])}
        
        if validated_data.get("total") is not None:
            record["total"] = {"value": str(validated_data["total"])}
        
        # 日付フィールド
        if validated_data.get("due_date"):
            record["due_date"] = {"value": validated_data["due_date"]}
        
        payload = {
            "app": self.app_id,
            "record": record
        }
        
        logger.info(f"📤 Kintone API呼び出し: POST {url}")
        logger.info(f"📦 送信ペイロード: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        
        # 3. API呼び出し
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            record_id = result.get("id")
            
            if not record_id:
                raise KintoneAPIError("レコードIDが返されませんでした")
            
            logger.info(f"✅ レコード作成成功: ID={record_id}")
            return int(record_id)
            
        except requests.exceptions.HTTPError as e:
            # Kintone APIのエラーレスポンスを解析
            try:
                error_detail = response.json()
                error_message = error_detail.get("message", str(e))
                error_code = error_detail.get("code", "UNKNOWN")
            except:
                error_message = str(e)
                error_code = "UNKNOWN"
            
            full_error_message = (
                f"Kintone APIエラー [{error_code}]: {error_message}\n"
                f"ステータスコード: {response.status_code}"
            )
            logger.error(full_error_message)
            raise KintoneAPIError(full_error_message)
            
        except requests.exceptions.Timeout:
            error_message = "Kintone APIタイムアウト（30秒）"
            logger.error(error_message)
            raise KintoneAPIError(error_message)
            
        except requests.exceptions.RequestException as e:
            error_message = f"Kintone API接続エラー: {str(e)}"
            logger.error(error_message)
            raise KintoneAPIError(error_message)
    
    def create_records_bulk(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        複数レコードを一括作成（エラーハンドリング付き）
        
        Args:
            records: レコードデータのリスト
            
        Returns:
            結果サマリー（成功数、失敗数、エラー詳細）
        """
        results = {
            "success": [],
            "failed": [],
            "total": len(records),
            "success_count": 0,
            "failed_count": 0
        }
        
        logger.info(f"一括レコード作成開始: {len(records)}件")
        
        for idx, data in enumerate(records, 1):
            try:
                record_id = self.create_record(data)
                results["success"].append({
                    "index": idx,
                    "record_id": record_id,
                    "data": data
                })
                results["success_count"] += 1
                
                logger.info(
                    f"✅ [{idx}/{len(records)}] レコード作成成功: "
                    f"ID={record_id}, ベンダー={data.get('vendor')}"
                )
                
            except (KintoneValidationError, KintoneAPIError) as e:
                results["failed"].append({
                    "index": idx,
                    "error": str(e),
                    "data": data
                })
                results["failed_count"] += 1
                
                logger.error(f"❌ [{idx}/{len(records)}] レコード作成失敗: {str(e)}")
        
        logger.info(
            f"一括レコード作成完了: 成功={results['success_count']}, "
            f"失敗={results['failed_count']}"
        )
        
        return results
    
    def update_record(self, record_id: int, data: Dict[str, Any]) -> None:
        """
        レコードを更新（バリデーション付き）
        
        Args:
            record_id: レコードID
            data: 更新データ
            
        Raises:
            KintoneValidationError: バリデーションエラー
            KintoneAPIError: API呼び出しエラー
        """
        # データ検証
        validated_data = self.validate_record_data(data)
        
        url = f"{self.domain}/k/v1/record.json"
        
        # レコード構築（Noneの場合はフィールドを含めない）
        record = {
            "vendor": {"value": validated_data.get("vendor", "")}
        }
        
        if validated_data.get("subtotal") is not None:
            record["subtotal"] = {"value": str(validated_data["subtotal"])}
        
        if validated_data.get("total") is not None:
            record["total"] = {"value": str(validated_data["total"])}
        
        if validated_data.get("due_date"):
            record["due_date"] = {"value": validated_data["due_date"]}
        
        payload = {
            "app": self.app_id,
            "id": record_id,
            "record": record
        }
        
        logger.debug(f"レコード更新: ID={record_id}")
        
        try:
            response = requests.put(url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            logger.info(f"✅ レコード更新成功: ID={record_id}")
            
        except requests.exceptions.HTTPError as e:
            try:
                error_detail = response.json()
                error_message = error_detail.get("message", str(e))
            except:
                error_message = str(e)
            
            full_error_message = f"レコード更新エラー: {error_message}"
            logger.error(full_error_message)
            raise KintoneAPIError(full_error_message)
            
        except requests.exceptions.RequestException as e:
            error_message = f"レコード更新接続エラー: {str(e)}"
            logger.error(error_message)
            raise KintoneAPIError(error_message)
    
    def get_record(self, record_id: int) -> Dict[str, Any]:
        """
        レコードを取得
        
        Args:
            record_id: レコードID
            
        Returns:
            レコードデータ
            
        Raises:
            KintoneAPIError: API呼び出しエラー
        """
        url = f"{self.domain}/k/v1/record.json"
        params = {
            "app": self.app_id,
            "id": record_id
        }
        
        logger.debug(f"レコード取得: ID={record_id}")
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            logger.info(f"✅ レコード取得成功: ID={record_id}")
            return response.json().get("record", {})
            
        except requests.exceptions.HTTPError as e:
            try:
                error_detail = response.json()
                error_message = error_detail.get("message", str(e))
            except:
                error_message = str(e)
            
            full_error_message = f"レコード取得エラー: {error_message}"
            logger.error(full_error_message)
            raise KintoneAPIError(full_error_message)
            
        except requests.exceptions.RequestException as e:
            error_message = f"レコード取得接続エラー: {str(e)}"
            logger.error(error_message)
            raise KintoneAPIError(error_message)


# ============================================================
# ローカルテスト用
# ============================================================

if __name__ == "__main__":
    """ローカルテスト用"""
    import sys
    from dotenv import load_dotenv
    
    # ロギング設定
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    load_dotenv()
    
    try:
        # クライアント初期化
        client = KintoneClient()
        
        # テストデータ
        test_records = [
            {
                "vendor": "株式会社 A商事",
                "subtotal": 10000,
                "total": 11000,
                "due_date": "2025-12-31"
            },
            {
                "vendor": "",  # ← エラー: ベンダー名が空
                "subtotal": 5000,
                "total": 5500,
                "due_date": "2025-11-30"
            },
            {
                "vendor": "（株）B産業",
                "subtotal": -1000,  # ← エラー: 負の値
                "total": 2000,
                "due_date": "2025-10-31"
            }
        ]
        
        # 一括作成
        print("\n" + "=" * 60)
        print("一括レコード作成を開始します...")
        print("=" * 60 + "\n")
        
        results = client.create_records_bulk(test_records)
        
        # 結果サマリー
        print("\n" + "=" * 60)
        print("結果サマリー")
        print("=" * 60)
        print(f"総レコード数: {results['total']}")
        print(f"成功: {results['success_count']} 件")
        print(f"失敗: {results['failed_count']} 件")
        
        if results["failed"]:
            print("\n失敗したレコード:")
            for failed in results["failed"]:
                print(f"  [{failed['index']}] {failed['error']}")
        
        if results["success"]:
            print("\n成功したレコード:")
            for success in results["success"]:
                print(f"  [{success['index']}] レコードID: {success['record_id']}")
    
    except Exception as e:
        logger.error(f"テスト実行エラー: {str(e)}", exc_info=True)
        sys.exit(1)
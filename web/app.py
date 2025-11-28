import os
import uuid
import hashlib
from flask import Flask, request, jsonify
from google.cloud import storage
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', static_url_path='')

# === 環境変数 ===
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT_ID')
INPUT_BUCKET = os.environ.get('INPUT_BUCKET')

# 必須環境変数のチェック
if not PROJECT_ID or not INPUT_BUCKET:
    raise ValueError(
        "環境変数が設定されていません:\n"
        f"  GOOGLE_CLOUD_PROJECT_ID: {'✓' if PROJECT_ID else '✗'}\n"
        f"  INPUT_BUCKET: {'✓' if INPUT_BUCKET else '✗'}"
    )

def get_storage_client():
    """GCS クライアント取得"""
    return storage.Client(project=PROJECT_ID)

@app.route('/', methods=['GET'])
def index():
    """トップページ"""
    return app.send_static_file('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    """PDFファイルをGCSにアップロード"""
    files = request.files.getlist('files')
    
    if not files or len(files) == 0:
        return jsonify({
            'success': False,
            'message': 'ファイルを選択してください'
        }), 400

    # PDFファイルのみフィルタ
    pdf_files = [f for f in files if f.filename and f.filename.lower().endswith('.pdf')]
    
    if len(pdf_files) == 0:
        return jsonify({
            'success': False,
            'message': 'PDFファイルを選択してください'
        }), 400

    uploaded_files = []
    failed_files = []
    duplicate_files = []

    try:
        storage_client = get_storage_client()
        bucket = storage_client.bucket(INPUT_BUCKET)
        
        for file in pdf_files:
            try:
                # 1. ファイルハッシュを計算（重複チェック用）
                file_content = file.read()
                file_hash = hashlib.sha256(file_content).hexdigest()
                
                # ※重要: read()後はファイル位置を先頭に戻す
                file.seek(0)
                
                # 2. ハッシュベースのファイル名を生成
                save_filename = f"{file_hash}.pdf"
                
                # 3. GCS上での重複チェック
                blob = bucket.blob(save_filename)
                
                if blob.exists():
                    # 重複検知: 既にアップロード済み
                    app.logger.warning(f"Duplicate detected: {file.filename} (hash: {file_hash[:8]}...)")
                    duplicate_files.append({
                        'original_name': file.filename,
                        'status': 'duplicate',
                        'message': '既にアップロード済みのファイルです'
                    })
                    continue  # 次のファイルへ
                
                # 4. 重複なし → アップロード実行
                # メタデータに元のファイル名を保存
                blob.metadata = {
                    'original_filename': file.filename,
                    'file_hash': file_hash,
                    'upload_timestamp': str(uuid.uuid4())  # アップロード識別用
                }
                blob.upload_from_string(file_content, content_type='application/pdf')
                
                uploaded_files.append({
                    'original_name': file.filename,
                    'uploaded_name': save_filename,
                    'file_hash': file_hash[:8],  # 先頭8文字のみ表示
                    'size': len(file_content)
                })
                
                app.logger.info(f"Uploaded: {save_filename} (original: {file.filename})")
                
            except Exception as e:
                app.logger.error(f"Upload failed for {file.filename}: {e}")
                failed_files.append({
                    'filename': file.filename,
                    'error': str(e)
                })
        
        # レスポンス作成
        total_processed = len(uploaded_files) + len(duplicate_files) + len(failed_files)
        
        if len(failed_files) == 0 and len(duplicate_files) == 0:
            # 全て成功
            return jsonify({
                'success': True,
                'message': f'✅ {len(uploaded_files)}個のファイルをアップロードしました',
                'uploaded': uploaded_files
            }), 200
        elif len(uploaded_files) == 0 and len(duplicate_files) == 0:
            # 全て失敗
            return jsonify({
                'success': False,
                'message': '❌ アップロードに失敗しました',
                'failed': failed_files
            }), 500
        else:
            # 一部成功・重複・失敗が混在
            message_parts = []
            if len(uploaded_files) > 0:
                message_parts.append(f'{len(uploaded_files)}個成功')
            if len(duplicate_files) > 0:
                message_parts.append(f'{len(duplicate_files)}個重複')
            if len(failed_files) > 0:
                message_parts.append(f'{len(failed_files)}個失敗')
            
            return jsonify({
                'success': len(uploaded_files) > 0,
                'message': f'⚠️ {", ".join(message_parts)}',
                'uploaded': uploaded_files,
                'duplicates': duplicate_files,
                'failed': failed_files
            }), 207
        
    except Exception as e:
        app.logger.error(f"Upload error: {e}")
        return jsonify({
            'success': False,
            'message': f'エラーが発生しました: {str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)

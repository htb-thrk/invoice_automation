import os
import uuid
from flask import Flask, request, jsonify
from google.cloud import storage
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', static_url_path='')

# === 環境変数 ===
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT_ID', 'htbwebsite-chatbot-462005')
INPUT_BUCKET = os.environ.get('INPUT_BUCKET', 'htb-energy-contact-center-invoice-input')

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

    try:
        storage_client = get_storage_client()
        bucket = storage_client.bucket(INPUT_BUCKET)
        
        for file in pdf_files:
            try:
                # ファイル名を安全化（拡張子を保持）
                original_name = file.filename
                name_without_ext = os.path.splitext(original_name)[0]
                safe_name = secure_filename(name_without_ext)
                unique_filename = f"{uuid.uuid4().hex}_{safe_name}.pdf"
                
                # GCSにアップロード
                blob = bucket.blob(unique_filename)
                blob.upload_from_file(file, content_type='application/pdf')
                
                uploaded_files.append({
                    'original_name': file.filename,
                    'uploaded_name': unique_filename,
                    'size': file.content_length or 0
                })
                
                app.logger.info(f"Uploaded: {unique_filename}")
                
            except Exception as e:
                app.logger.error(f"Upload failed for {file.filename}: {e}")
                failed_files.append({
                    'filename': file.filename,
                    'error': str(e)
                })
        
        # レスポンス作成
        if len(failed_files) == 0:
            return jsonify({
                'success': True,
                'message': f'✅ {len(uploaded_files)}個のファイルをアップロードしました',
                'uploaded': uploaded_files
            }), 200
        elif len(uploaded_files) == 0:
            return jsonify({
                'success': False,
                'message': '❌ アップロードに失敗しました',
                'failed': failed_files
            }), 500
        else:
            return jsonify({
                'success': True,
                'message': f'⚠️ {len(uploaded_files)}個成功、{len(failed_files)}個失敗',
                'uploaded': uploaded_files,
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

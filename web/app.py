import os
import uuid
from flask import Flask, request, jsonify
from google.cloud import storage
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='static', static_url_path='')

# === 設定 ===
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'htb-energy-contact-center-invoice-input')

# GCS クライアントは遅延初期化（認証エラーを回避）
def get_storage_client():
    return storage.Client()

# === ルートは静的 index.html を返す ===
@app.route('/', methods=['GET'])
def index():
    return app.send_static_file('index.html')

# === アップロード API — 複数ファイル対応 JSON を返す ===
@app.route('/upload', methods=['POST'])
def upload_api():
    files = request.files.getlist('files')
    
    if not files or len(files) == 0:
        return jsonify({'success': False, 'message': 'ファイルを選択してください。'}), 400

    # PDF ファイルのみをフィルタ
    pdf_files = [f for f in files if f.filename and f.filename.lower().endswith('.pdf')]
    
    if len(pdf_files) == 0:
        return jsonify({'success': False, 'message': 'PDFファイルを選択してください。'}), 400

    uploaded = []
    failed = []

    try:
        storage_client = get_storage_client()
        bucket = storage_client.bucket(BUCKET_NAME)
        
        for file in pdf_files:
            try:
                # filename を安全にする（衝突回避のため UUID を付与）
                filename = secure_filename(file.filename)
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                
                blob = bucket.blob(unique_name)
                blob.upload_from_file(file, content_type='application/pdf')
                
                gcs_path = f"gs://{BUCKET_NAME}/{unique_name}"
                uploaded.append({'filename': file.filename, 'gcs_path': gcs_path})
            except Exception as e:
                print(f"Upload error for {file.filename}: {e}")
                failed.append({'filename': file.filename, 'error': str(e)})
        
        # 結果メッセージ作成
        if len(failed) == 0:
            message = f'✅ {len(uploaded)}個のファイルをアップロード完了'
        elif len(uploaded) == 0:
            message = f'❌ すべてのファイルのアップロードに失敗しました'
            return jsonify({'success': False, 'message': message, 'failed': failed}), 500
        else:
            message = f'⚠️ {len(uploaded)}個成功、{len(failed)}個失敗'
        
        return jsonify({
            'success': True,
            'message': message,
            'uploaded': uploaded,
            'failed': failed
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'success': False, 'message': f'アップロードに失敗しました: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)

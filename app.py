import os
from flask import Flask, request, render_template_string
from google.cloud import storage

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\bpr\Documents\invoice_automation\htbwebsite-chatbot-462005-96b72ed68c17.json"

app = Flask(__name__)

# === 設定 ===
BUCKET_NAME = "htb-energy-contact-center-invoice-input"
storage_client = storage.Client()

# === HTMLテンプレート ===
UPLOAD_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Invoice Uploader</title>
</head>
<body style="font-family:sans-serif; margin:40px;">
  <h2>請求書PDFアップロード</h2>
  <form method="POST" enctype="multipart/form-data">
      <input type="file" name="file" accept="application/pdf" required>
      <button type="submit">アップロード</button>
  </form>
  {% if message %}
    <p style="color: green;">{{ message }}</p>
  {% endif %}
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def upload_file():
    message = None
    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename.endswith(".pdf"):
            blob_name = file.filename
            bucket = storage_client.bucket(BUCKET_NAME)
            blob = bucket.blob(blob_name)
            blob.upload_from_file(file, content_type="application/pdf")
            message = f"✅ アップロード完了: gs://{BUCKET_NAME}/{blob_name}"
        else:
            message = "PDFファイルを選択してください。"
    return render_template_string(UPLOAD_HTML, message=message)


if __name__ == "__main__":
    # ローカル実行用
    app.run(host="0.0.0.0", port=8080, debug=True)

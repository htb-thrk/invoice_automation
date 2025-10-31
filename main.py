import functions_framework
from modules.document_ai_utils import process_pdf
from modules.kintone_writer import post_to_kintone
from functions.json_saver import save_json

@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    data = cloud_event.data
    bucket, name = data["bucket"], data["name"]
    print(f"Triggered by file: gs://{bucket}/{name}")

    result = process_pdf(bucket, name)
    print("Extracted result:", result)

    # kintone へ書き込み
    post_to_kintone(result)
    out_uri = save_json(bucket, name, result)
    print(f"Saved JSON to {out_uri}")

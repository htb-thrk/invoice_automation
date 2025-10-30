import functions_framework
from functions.document_ai_utils import process_pdf
from functions.excel_updater import write_to_sheet

@functions_framework.cloud_event
def on_file_finalized(cloud_event):
    """GCSトリガーでPDFがアップされたら発火"""
    data = cloud_event.data
    bucket = data["bucket"]
    name = data["name"]

    print(f"Triggered by file: gs://{bucket}/{name}")
    result = process_pdf(bucket, name)
    print("Extracted result:", result)

    write_to_sheet(result)
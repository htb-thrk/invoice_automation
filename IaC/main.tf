terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = "htbwebsite-chatbot-462005"
  region  = "asia-northeast1"
}

# Cloud Functions (Gen2)
resource "google_cloudfunctions2_function" "process_pdf_invoice" {
  name        = "process_pdf_invoice"
  location    = "asia-northeast1"

  build_config {
    runtime     = "python311"
    entry_point = "on_file_finalized"
    source {
      storage_source {
        bucket = "your-source-code-bucket"
        object = "function-source.zip"
      }
    }
  }

  service_config {
    available_memory   = "256M"
    service_account_email = "docai-function-sa@htbwebsite-chatbot-462005.iam.gserviceaccount.com"

    environment_variables = {
      PROJECT_ID    = "htbwebsite-chatbot-462005"
      LOCATION      = "us"
      PROCESSOR_ID  = "262737a70f618b3"
      OUTPUT_BUCKET = "htb-energy-contact-center-invoice-output"
    }
  }

  event_trigger {
    event_type = "google.cloud.storage.object.v1.finalized"
    trigger_region = "asia-northeast1"
    event_filters {
      attribute = "bucket"
      value     = "htb-energy-contact-center-invoice-input"
    }
  }
}
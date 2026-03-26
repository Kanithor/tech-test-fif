# ─── Terraform — Pipeline de Ventas GCP ──────────────────────────────────────
#
# Recursos desplegados:
#   • Service Account con roles mínimos necesarios
#   • Pub/Sub: tópico + suscripción push hacia Cloud Run
#   • Cloud Run: servicio contenedorizado (ventas-subscriber)
# ─────────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# ─── Variables ────────────────────────────────────────────────────────────────

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region para Cloud Run y Artifact Registry"
  type        = string
  default     = "us-central1"
}

variable "container_image" {
  description = "URI completa de la imagen en Artifact Registry"
  type        = string
  default     = "us-central1-docker.pkg.dev/tech-test-fif/ventas-repo/ventas-subscriber:latest"
}

variable "topic_name" {
  description = "Nombre del tópico Pub/Sub"
  type        = string
  default     = "ventas-topic"
}

variable "subscription_name" {
  description = "Nombre de la suscripción push"
  type        = string
  default     = "ventas-push-sub"
}

variable "cloud_run_service_name" {
  description = "Nombre del servicio Cloud Run"
  type        = string
  default     = "ventas-subscriber"
}

variable "bq_dataset" {
  description = "Nombre del dataset BigQuery"
  type        = string
  default     = "ventas_ds"
}

variable "bq_table" {
  description = "Nombre de la tabla BigQuery"
  type        = string
  default     = "ventas_procesadas"
}

# ─── Provider ─────────────────────────────────────────────────────────────────

provider "google" {
  project = var.project_id
  region  = var.region
}

# ─── APIs requeridas ──────────────────────────────────────────────────────────

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "bigquery.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# ─── Service Account — Cloud Run ──────────────────────────────────────────────

resource "google_service_account" "cloud_run_sa" {
  project      = var.project_id
  account_id   = "sa-ventas-cloudrun"
  display_name = "SA Cloud Run"
  description  = "Cuenta de servicio para el servicio Cloud Run ventas-subscriber"

  depends_on = [google_project_service.apis]
}

# Permiso para insertar filas en BigQuery
resource "google_project_iam_member" "bq_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Permiso para ejecutar jobs de BigQuery (necesario para streaming inserts)
resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# ─── Pub/Sub Topic ────────────────────────────────────────────────────────────

resource "google_pubsub_topic" "ventas_topic" {
  project = var.project_id
  name    = var.topic_name

  # Retención de mensajes no consumidos: 7 días
  message_retention_duration = "604800s"

  labels = {
    sistema = "ventas"
    env     = "produccion"
  }

  depends_on = [google_project_service.apis]
}

# ─── Cloud Run Service ────────────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "ventas_subscriber" {
  project  = var.project_id
  name     = var.cloud_run_service_name
  location = var.region

  # Solo acepta tráfico interno (Pub/Sub push); no expuesto a internet
  ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.cloud_run_sa.email

    containers {
      image = var.container_image

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "BQ_DATASET"
        value = var.bq_dataset
      }
      env {
        name  = "BQ_TABLE"
        value = var.bq_table
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      # Health check para Cloud Run
      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 10
        period_seconds        = 30
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
  }

  depends_on = [
    google_project_service.apis,
    google_service_account.cloud_run_sa,
  ]
}

# ─── Service Account — Pub/Sub Invoker ───────────────────────────────────────
# Cuenta separada con privilegio mínimo: solo puede invocar el Cloud Run

resource "google_service_account" "pubsub_invoker_sa" {
  project      = var.project_id
  account_id   = "sa-ventas-pubsub-invoker"
  display_name = "SA Pub/Sub → Cloud Run Invoker"
  description  = "Permite a Pub/Sub autenticar e invocar el Cloud Run ventas-subscriber"

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "pubsub_can_invoke" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.ventas_subscriber.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker_sa.email}"
}

# ─── Pub/Sub Push Subscription ────────────────────────────────────────────────

resource "google_pubsub_subscription" "ventas_push_sub" {
  project = var.project_id
  name    = var.subscription_name
  topic   = google_pubsub_topic.ventas_topic.name

  push_config {
    # El endpoint apunta al path /pubsub del servicio Cloud Run
    push_endpoint = "${google_cloud_run_v2_service.ventas_subscriber.uri}/pubsub"

    # Token OIDC firmado por el SA invoker para autenticar la llamada
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker_sa.email
    }
  }

  # Tiempo máximo para procesar antes de considerar NACK
  ack_deadline_seconds = 30

  # Retener mensajes no procesados por 1 día
  message_retention_duration = "86400s"

  # Política de reintento exponencial
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  labels = {
    sistema = "ventas"
    env     = "produccion"
  }

  depends_on = [
    google_cloud_run_v2_service.ventas_subscriber,
    google_cloud_run_v2_service_iam_member.pubsub_can_invoke,
  ]
}

# ─── Outputs ──────────────────────────────────────────────────────────────────

output "cloud_run_url" {
  description = "URL del servicio Cloud Run ventas-subscriber"
  value       = google_cloud_run_v2_service.ventas_subscriber.uri
}

output "pubsub_topic_id" {
  description = "ID completo del tópico Pub/Sub"
  value       = google_pubsub_topic.ventas_topic.id
}

output "cloud_run_sa_email" {
  description = "Email de la Service Account de Cloud Run"
  value       = google_service_account.cloud_run_sa.email
}

output "pubsub_invoker_sa_email" {
  description = "Email de la Service Account del invoker Pub/Sub"
  value       = google_service_account.pubsub_invoker_sa.email
}

output "bigquery_table_ref" {
  description = "Referencia completa a la tabla BigQuery"
  value       = "${var.project_id}.${var.bq_dataset}.${var.bq_table}"
}

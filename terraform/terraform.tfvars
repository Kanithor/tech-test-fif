project_id      = "tech-test-fif"
region          = "us-central1"
container_image = "us-central1-docker.pkg.dev/tech-test-fif/ventas-repo/ventas-subscriber:latest"

topic_name             = "ventas-topic"
subscription_name      = "ventas-push-sub"
cloud_run_service_name = "ventas-subscriber"
bq_dataset             = "ventas_ds"
bq_table               = "ventas_procesadas"

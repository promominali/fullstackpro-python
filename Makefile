# Makefile to bootstrap core GCP resources for this app.
#
# Usage (examples):
#   PROJECT_ID=my-project REGION=us-central1 make gcp-bootstrap
#   PROJECT_ID=my-project REGION=us-central1 PUBSUB_TOPIC=fullstack-jobs make gcp-create-pubsub-topic
#
# Deployment of Cloud Run services is done via GitHub Actions workflows in
# .github/workflows/deploy-*.yml. Those workflows will create/update the
# Cloud Run services on first deploy.

# Optional local config overrides (see config.mk)
-include config.mk

PROJECT_ID       ?= fullstackpro-python
REGION           ?= us-central1

# Artifact Registry
ARTIFACT_REPO        ?= fullstackpro-python
ARTIFACT_REPO_FORMAT ?= docker

# Cloud SQL (Postgres)
DB_INSTANCE      ?= fullstack-sql
DB_TIER          ?= db-f1-micro
DB_NAME          ?= app
DB_USER          ?= appuser
# IMPORTANT: do NOT commit real passwords; pass DB_PASSWORD via env or override on the CLI.
DB_PASSWORD      ?= change-me

# Pub/Sub
PUBSUB_TOPIC     ?= fullstackpro

# Redis (Memorystore)
REDIS_INSTANCE   ?= fullstack-redis
REDIS_TIER       ?= BASIC
REDIS_SIZE_GB    ?= 1
REDIS_VERSION    ?= redis_7_0

.PHONY: gcp-check-vars gcp-enable-apis gcp-create-artifact-registry \
        gcp-create-sql-instance gcp-create-sql-db gcp-create-sql-user \
        gcp-create-pubsub-topic gcp-create-redis-instance gcp-bootstrap

## Internal: ensure PROJECT_ID is set to something non-empty
gcp-check-vars:
	@if [ -z "$(PROJECT_ID)" ]; then \
	  echo "[ERROR] PROJECT_ID is empty. Set it in config.mk or via CLI (e.g. PROJECT_ID=fullstackpro-python make gcp-bootstrap)"; \
	  exit 1; \
	fi

## Enable core GCP APIs required by this project
gcp-enable-apis: gcp-check-vars
	gcloud services enable \
	  run.googleapis.com \
	  artifactregistry.googleapis.com \
	  sqladmin.googleapis.com \
	  redis.googleapis.com \
	  pubsub.googleapis.com \
	  cloudbuild.googleapis.com \
	  --project $(PROJECT_ID)

## Create Artifact Registry repository for container images
gcp-create-artifact-registry: gcp-check-vars
	gcloud artifacts repositories create $(ARTIFACT_REPO) \
	  --repository-format=$(ARTIFACT_REPO_FORMAT) \
	  --location=$(REGION) \
	  --description="Fullstack app images" \
	  --project=$(PROJECT_ID) || echo "Repository may already exist; continuing."

## Create a Cloud SQL Postgres instance (small default tier)
gcp-create-sql-instance: gcp-check-vars
	gcloud sql instances create $(DB_INSTANCE) \
	  --project=$(PROJECT_ID) \
	  --database-version=POSTGRES_15 \
	  --tier=$(DB_TIER) \
	  --region=$(REGION)

## Create application database inside the Cloud SQL instance
gcp-create-sql-db: gcp-check-vars
	gcloud sql databases create $(DB_NAME) \
	  --instance=$(DB_INSTANCE) \
	  --project=$(PROJECT_ID)

## Create application DB user (password provided via DB_PASSWORD)
gcp-create-sql-user: gcp-check-vars
	@if [ "$(DB_PASSWORD)" = "M0min@liPro" ]; then \
	  echo "[WARN] You're using the default DB_PASSWORD. Override it: DB_PASSWORD=your-strong-password make gcp-create-sql-user"; \
	fi
	gcloud sql users create $(DB_USER) \
	  --instance=$(DB_INSTANCE) \
	  --password=$(DB_PASSWORD) \
	  --project=$(PROJECT_ID)

## Create Pub/Sub topic for background jobs
gcp-create-pubsub-topic: gcp-check-vars
	gcloud pubsub topics create $(PUBSUB_TOPIC) \
	  --project=$(PROJECT_ID) || echo "Topic may already exist; continuing."

## Create Redis (Memorystore) instance for caching
gcp-create-redis-instance: gcp-check-vars
	gcloud redis instances create $(REDIS_INSTANCE) \
	  --size=$(REDIS_SIZE_GB) \
	  --region=$(REGION) \
	  --tier=$(REDIS_TIER) \
	  --redis-version=$(REDIS_VERSION) \
	  --project=$(PROJECT_ID) || echo "Redis instance may already exist; continuing."

## Convenience target: run the common bootstrap steps
# This will:
#   - enable required APIs
#   - create the Artifact Registry repo
#   - create the Cloud SQL instance, DB, and DB user
#   - create the Pub/Sub topic
#   - create a Redis / Memorystore instance (for REDIS_URL)
# You still need to:
#   - configure Cloud SQL connectivity for Cloud Run
#   - configure VPC / network connectivity for Redis + Cloud Run
#   - configure GitHub secrets used by the deploy workflows

gcp-bootstrap: gcp-enable-apis gcp-create-artifact-registry gcp-create-sql-instance gcp-create-sql-db gcp-create-sql-user gcp-create-pubsub-topic gcp-create-redis-instance
	@echo "\n[INFO] GCP bootstrap complete. Next steps:"
	@echo "  1) Configure Cloud SQL connectivity (e.g. instance connection name, authorized networks or VPC)."
	@echo "  2) Retrieve Redis instance host/port and set REDIS_URL / network for Cloud Run (e.g. Memorystore private IP)."
	@echo "  3) In GitHub repo settings, add Actions secrets: GCP_SA_KEY, DATABASE_URL, REDIS_URL, SECRET_KEY."
	@echo "  4) Push to main and let GitHub Actions (ci/deploy-web/deploy-worker) build and deploy to Cloud Run."

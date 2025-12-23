# fullstackpro-python

Full-stack Python app (FastAPI) designed for deployment to Google Cloud Run with GitHub Actions.

This README describes the full sequence of steps to:
- Run the app locally (Docker Compose)
- Bootstrap required GCP resources (Makefile)
- Configure GitHub Actions
- Deploy to Cloud Run via GitHub Actions

---

## 1. Prerequisites

- Python 3.11+ (for local tooling, optional if you only use Docker)
- Docker + Docker Compose
- `gcloud` CLI installed and authenticated
- A GCP project (this repo assumes `fullstackpro-python`)
- GitHub repo: `promominali/fullstackpro-python`

Key non-secret defaults are in `config.mk`:

```makefile path=null start=null
PROJECT_ID=fullstackpro-python
REGION=us-central1
GITHUB_USER=promominali
ARTIFACT_REPO=fullstackpro-python
```

You can override these by editing `config.mk` or with CLI env vars when calling `make`.

---

## 2. Run locally with Docker Compose

1. Clone the repo:

```bash path=null start=null
git clone https://github.com/promominali/fullstackpro-python.git
cd fullstackpro-python
```

2. Create a local env file from the example and adjust as needed:

```bash path=null start=null
cp .env.example .env
# Edit .env to tweak DB/Redis URLs or secrets for local dev
```

3. Start the stack (Postgres, Redis, web, worker):

```bash path=null start=null
docker compose up --build
```

4. Verify locally:

- App: http://localhost:8000/
- Health: http://localhost:8000/healthz
- Register: http://localhost:8000/auth/register
- Login: http://localhost:8000/auth/login
- Dashboard (requires login): http://localhost:8000/dashboard

Stop with `Ctrl+C` and `docker compose down` when done.

---

## 3. Bootstrap GCP resources (Makefile)

> These steps create core GCP infrastructure. Deployment to Cloud Run is handled separately by GitHub Actions.

1. Ensure `config.mk` has the desired values (defaults are already set to):

```makefile path=null start=null
PROJECT_ID=fullstackpro-python
REGION=us-central1
ARTIFACT_REPO=fullstackpro-python
```

2. Run the bootstrap target (from the repo root):

```bash path=null start=null
make gcp-bootstrap
```

This will:

- Enable core GCP APIs (Cloud Run, Artifact Registry, SQL Admin, Redis, Pub/Sub, Cloud Build)
- Create an Artifact Registry repo `fullstackpro-python` in `us-central1`
- Create a Cloud SQL Postgres instance `fullstack-sql` in `us-central1`
- Create DB `app` and DB user `appuser`
- Create Pub/Sub topic `fullstack-jobs`

3. Capture connection details for later:

- Cloud SQL instance connection name:

```bash path=null start=null
gcloud sql instances describe fullstack-sql \
  --project=fullstackpro-python \
  --format='value(connectionName)'
```

You will use this to construct your `DATABASE_URL`.

---

## 4. Prepare runtime configuration (DATABASE_URL, REDIS_URL, SECRET_KEY)

1. Construct a `DATABASE_URL` for SQLAlchemy, for example:

```text path=null start=null
postgresql+psycopg2://appuser:YOUR_DB_PASSWORD@HOST:PORT/app
```

Where:

- `appuser` – DB user created by the Makefile
- `YOUR_DB_PASSWORD` – the password you set via `DB_PASSWORD` when running `make gcp-create-sql-user` / `gcp-bootstrap`
- `HOST` / `PORT` – from your Cloud SQL connection method (public IP or private/VPC connector)

2. Decide on Redis / cache:

- For production, create a Memorystore Redis instance and construct a `REDIS_URL` like:

```text path=null start=null
redis://REDIS_INTERNAL_IP:6379/0
```

3. Generate a strong `SECRET_KEY` for signing session cookies, e.g. with Python:

```bash path=null start=null
python - << 'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
```

---

## 5. Configure GitHub Actions secrets

In the GitHub repo `promominali/fullstackpro-python`, go to:

- **Settings → Secrets and variables → Actions → New repository secret**

Create the following secrets:

- `GCP_SA_KEY` – JSON for a GCP service account used by GitHub Actions to deploy
  - This SA should have at minimum:
    - `roles/run.admin`
    - `roles/artifactregistry.writer`
    - `roles/iam.serviceAccountUser` for the Cloud Run runtime service accounts
- `DATABASE_URL` – value constructed in step 4
- `REDIS_URL` – Redis / Memorystore URL (or a development Redis instance if used)
- `SECRET_KEY` – strong random value from step 4

The project and region are already fixed in the workflows to:

- `PROJECT_ID = fullstackpro-python`
- `REGION = us-central1`

---

## 6. How CI and deployment work

There are three key workflows in `.github/workflows/`:

1. **CI** – `.github/workflows/ci.yml`

   - Runs on every push and PR
   - Installs dependencies and compiles Python files for basic validation

2. **Deploy Web** – `.github/workflows/deploy-web.yml`

   - Triggers on push to `main` when relevant files change
   - Uses `GCP_SA_KEY` to authenticate
   - Builds and pushes the web image:

   ```text path=null start=null
   us-central1-docker.pkg.dev/fullstackpro-python/fullstackpro-python/web:latest
   ```

   - Deploys Cloud Run service `fullstack-web` in `us-central1`
   - Sets environment variables from GitHub secrets:
     - `DATABASE_URL`
     - `REDIS_URL`
     - `ENVIRONMENT=prod`
     - `SECRET_KEY`

3. **Deploy Worker** – `.github/workflows/deploy-worker.yml`

   - Triggers on push to `main` when relevant files change
   - Builds and pushes the worker image:

   ```text path=null start=null
   us-central1-docker.pkg.dev/fullstackpro-python/fullstackpro-python/worker:latest
   ```

   - Deploys Cloud Run service `fullstack-worker` in `us-central1`
   - Sets environment variables:
     - `DATABASE_URL`
     - `REDIS_URL`
     - `ENVIRONMENT=prod`
     - `SECRET_KEY`
     - `GCP_PROJECT_ID=fullstackpro-python`
     - `PUBSUB_TOPIC=fullstack-jobs`

---

## 7. End-to-end deployment sequence (summary)

1. **Local sanity check (optional but recommended):**

   ```bash path=null start=null
git clone https://github.com/promominali/fullstackpro-python.git
cd fullstackpro-python
cp .env.example .env
docker compose up --build
   ```

2. **Bootstrap GCP resources:**

   ```bash path=null start=null
cd fullstackpro-python
make gcp-bootstrap
   ```

3. **Set up Cloud SQL connectivity and Redis/Memorystore**

   - Configure how Cloud Run will reach Cloud SQL (public IP + authorized networks or private IP + VPC connector).
   - Create a Memorystore Redis instance if needed, and note its internal IP.

4. **Prepare runtime values:**

   - Build `DATABASE_URL` using your Cloud SQL instance and app DB user
   - Build `REDIS_URL` using your Redis instance
   - Generate a strong `SECRET_KEY`

5. **Configure GitHub Actions secrets:**

   - Add `GCP_SA_KEY`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` to the repo secrets.

6. **Trigger deployment:**

   - Push (or merge) changes to the `main` branch:

   ```bash path=null start=null
git add .
git commit -m "Initial fullstackpro-python setup"  # include co-author line if desired
git push origin main
   ```

   - GitHub Actions will:
     - Run CI
     - Build and push images
     - Deploy `fullstack-web` and `fullstack-worker` to Cloud Run

7. **Configure Pub/Sub push subscription:**

   - In GCP, create a Pub/Sub subscription on topic `fullstack-jobs` with push endpoint:

   ```text path=null start=null
   https://<fullstack-worker-cloud-run-url>/pubsub/push
   ```

   - Ensure the Pub/Sub push service account has permission to invoke the worker Cloud Run service.

After these steps, your app should be live on Cloud Run with CI/CD driven by GitHub Actions.

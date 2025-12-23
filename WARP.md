# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Overview

This repository is a FastAPI-based full-stack Python app designed for deployment to Google Cloud Run. It consists of:
- A **web service** (`app.main:app`) that serves HTML views and a small JSON API.
- A **worker service** (`app.worker_main:worker_app`) that processes background jobs delivered via Pub/Sub push.
- Shared infrastructure code for configuration, database access, caching, authentication, and queues under the `app/` package.
- GCP bootstrap automation via the `Makefile` and deployment automation via GitHub Actions workflows in `.github/workflows/`.

## Common commands

All commands assume repository root as the working directory.

### Local stack via Docker Compose (recommended)

This is the primary way to run the full app locally (Postgres, Redis, web, worker):

```bash path=null start=null
cp .env.example .env   # one-time; customize as needed
docker compose up --build
```

- Web app: `http://localhost:8000/`
- Health: `http://localhost:8000/healthz`
- Auth views: `/auth/login`, `/auth/register`
- Dashboard (requires login): `/dashboard`

Shut down with `Ctrl+C` and then:

```bash path=null start=null
docker compose down
```

### Python environment and dependencies (non-Docker workflows)

CI uses Python 3.12 and installs from `requirements.txt`. To mirror that locally:

```bash path=null start=null
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Running the web app directly (without Docker)

The web service entrypoint matches `Dockerfile.web`:

```bash path=null start=null
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Static files are served from `app/static`, and templates from `app/templates`.

### Running the worker app directly (without Docker)

The worker service entrypoint matches `Dockerfile.worker`:

```bash path=null start=null
uvicorn app.worker_main:worker_app --host 0.0.0.0 --port 8081
```

(Port 8081 is suggested locally to avoid clashing with the web service; the container image itself uses 8080.)

### Basic "lint" / sanity check (matches CI)

There is no dedicated linter configured; CI currently performs a basic bytecode compilation check:

```bash path=null start=null
python -m compileall app
```

Run this locally before pushes to catch syntax errors similar to CI.

### Tests

There is currently no test suite wired into CI (the CI workflow contains only a placeholder step). If you add tests using `pytest`, typical commands will look like:

```bash path=null start=null
pytest              # run all tests
pytest path/to/test_file.py::TestClass::test_method  # run a single test
```

Adjust paths/names as appropriate for the actual test layout once it exists.

### GCP bootstrap via Makefile

The `Makefile` is used to provision core GCP infrastructure. Non-secret defaults live in `config.mk` (e.g. `PROJECT_ID=fullstackpro-python`, `REGION=us-central1`).

The main bootstrap command (from repo root):

```bash path=null start=null
make gcp-bootstrap
```

This will, using the configured `PROJECT_ID` and `REGION`:
- Enable core APIs (`run.googleapis.com`, `artifactregistry.googleapis.com`, `sqladmin.googleapis.com`, `redis.googleapis.com`, `pubsub.googleapis.com`, `cloudbuild.googleapis.com`).
- Create an Artifact Registry repository for container images.
- Create a Cloud SQL Postgres instance, database, and application DB user.
- Create a Pub/Sub topic for background jobs.

You can also run individual steps:

```bash path=null start=null
make gcp-enable-apis
make gcp-create-artifact-registry
make gcp-create-sql-instance
make gcp-create-sql-db
DB_PASSWORD=your-strong-password make gcp-create-sql-user
make gcp-create-pubsub-topic
```

### Deployment via GitHub Actions / Cloud Run

Deployments are handled by workflows in `.github/workflows/`:

- `ci.yml` – basic CI (dependency install + `python -m compileall app`).
- `deploy-web.yml` – builds `Dockerfile.web` and deploys `fullstack-web` to Cloud Run.
- `deploy-worker.yml` – builds `Dockerfile.worker` and deploys `fullstack-worker` to Cloud Run.

They expect the following GitHub Actions secrets to be configured (see `README.md` for details):
- `GCP_SA_KEY` – JSON for a GCP service account with deploy permissions.
- `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` – runtime configuration for both services.

The worker deploy additionally relies on:
- `GCP_PROJECT_ID` (fixed to `fullstackpro-python` in the workflow env).
- `PUBSUB_TOPIC` (fixed to `fullstack-jobs`).

## High-level architecture

### Application package (`app/`)

The `app` package contains all application logic shared by the web and worker services:

- **Configuration (`app/config.py`)**
  - Uses Pydantic `BaseSettings` to load configuration from environment variables and an optional `.env` file.
  - Key settings: `database_url`, `redis_url`, `secret_key`, `environment`, `gcp_project_id`, `gcp_region`, `pubsub_topic`, `cloud_run_service`.
  - `settings` is a module-level singleton created via `get_settings()` and cached with `lru_cache()`.

- **Database (`app/db.py`, `app/models.py`)**
  - `app.db` defines:
    - `Base`: SQLAlchemy `DeclarativeBase` used for ORM models.
    - `engine`: created from `settings.database_url` with `pool_pre_ping=True`.
    - `SessionLocal`: a `sessionmaker` yielding `Session` objects.
    - `get_db()`: FastAPI-style dependency that yields a DB session and ensures it is closed.
    - `session_scope()`: context manager for manual session management with commit/rollback handling.
  - `app.models` defines ORM models:
    - `User` with email, hashed password, flags (`is_active`, `is_superuser`), timestamps, and many-to-many `roles` via the `user_roles` association table.
    - `Role` with a unique `name` and back-reference to associated `users`.
    - `ExampleItem` as a sample domain model with `slug`, `name`, `description`, `created_at`, and a unique constraint on `slug`.

- **Authentication and authorization (`app/auth.py`, `app/deps.py`)**
  - `app.auth` provides:
    - Password hashing/verification via `passlib` (bcrypt).
    - Cookie-based session tokens signed with `itsdangerous` using `settings.secret_key`.
    - Helpers to set/clear a session cookie (`settings.session_cookie_name`).
    - Utilities to resolve the current user (`get_current_user`) and to enforce authentication/authorization (`require_authenticated_user`, `require_role`).
  - `app.deps` wraps these into reusable FastAPI dependencies:
    - `db_session_dep()` – yields a SQLAlchemy `Session` (delegates to `get_db()`).
    - `current_user_dep` – returns the current user or `None`.
    - `authenticated_user_dep` – returns the current user or raises `401`.
    - `role_required_dep(*roles)` – factory that returns a dependency enforcing role-based access.

- **Caching (`app/cache.py`)**
  - Provides a lazily-initialized async Redis client from `settings.redis_url` using `redis.asyncio`.
  - `cache_get` / `cache_set` for JSON-encoded values.
  - `cached(ttl=60, key_builder=None)` decorator for async functions that caches results in Redis with an auto-constructed or custom key.

- **Queues / background jobs (`app/queues.py`, `app/worker_main.py`)**
  - `app.queues`:
    - Lazily creates a `google.cloud.pubsub_v1.PublisherClient` only when `settings.gcp_project_id` and `settings.pubsub_topic` are set.
    - `publish_event(data: dict)` serializes the payload to JSON and publishes it to the configured Pub/Sub topic; it is a no-op if Pub/Sub is not configured (useful for local dev).
  - `app.worker_main` defines the worker FastAPI application:
    - `worker_app = FastAPI(...)` with a single `/pubsub/push` endpoint for Pub/Sub push.
    - The endpoint decodes the standard Pub/Sub push format, base64-decodes the message `data`, parses JSON into a payload, then dispatches based on `payload["type"]`.
    - Currently supports a `"process_item"` job type handled by `handle_process_item`, which demonstrates DB access by loading an `ExampleItem` by `item_id`.

- **Routing and views (`app/main.py`, `app/routes/*.py`)**
  - `app.main` defines the primary FastAPI web application:
    - Configures static files (`/static` → `app/static`) and Jinja2 templates (`app/templates`).
    - On `startup`, auto-creates all SQLAlchemy tables via `Base.metadata.create_all(engine)` (no migration system is currently in place).
    - Exposes:
      - `GET /healthz` – simple health check.
      - `GET /` – renders `index.html`.
    - Includes routers from `app.routes.auth`, `app.routes.views`, and `app.routes.api` with appropriate prefixes and tags.
  - `app.routes.auth`:
    - HTML form-based auth flows (`/auth/login`, `/auth/register`).
    - Uses `Form` parameters and SQLAlchemy queries to validate credentials or register new users.
    - On successful login/registration, creates a session token and sets a cookie, then redirects to `/dashboard`.
  - `app.routes.views`:
    - Defines `GET /dashboard` which requires authentication via `authenticated_user_dep`.
    - Queries recent `ExampleItem` rows and renders `dashboard.html` with both `user` and `items` in the template context.
  - `app.routes.api`:
    - `GET /api/items` – returns a JSON list of up to 100 `ExampleItem`s, cached via the `@cached(ttl=30)` decorator.
    - `POST /api/items/{item_id}/process` – requires an authenticated user and enqueues a `process_item` job to Pub/Sub via `publish_event`.

### Configuration and environment

- Non-secret defaults for GCP (project, region, image repo, GitHub user) live in `config.mk` and are imported by the `Makefile`.
- Runtime configuration for the application is primarily driven by environment variables read through `app.config.Settings` (backed by `.env` in local/dev and by Cloud Run environment variables in production).
- `.env.example` documents the key environment variables:
  - `ENVIRONMENT`, `SECRET_KEY`, `SESSION_COOKIE_NAME`.
  - `DATABASE_URL`, `REDIS_URL` for database and Redis connections.
  - `GCP_PROJECT_ID`, `GCP_REGION`, `PUBSUB_TOPIC` for Pub/Sub integration.

### Deployment topology

- Two Cloud Run services:
  - **`fullstack-web`** – runs the web FastAPI app (`app.main:app`) built from `Dockerfile.web`.
  - **`fullstack-worker`** – runs the worker FastAPI app (`app.worker_main:worker_app`) built from `Dockerfile.worker` and receives Pub/Sub push requests on `/pubsub/push`.
- Container images are pushed to Artifact Registry in the project/region configured in the Makefile and workflows.
- Both services rely on the same `DATABASE_URL`, `REDIS_URL`, and `SECRET_KEY` configuration, provided via GitHub Actions secrets at deploy time.
- A Pub/Sub topic (default `fullstack-jobs`) delivers background job payloads to the worker via an HTTP push subscription.

## Notes for future agents

- There is no migration framework wired up; the web app currently auto-creates tables on startup. Schema changes to models may require manual DB migration steps.
- CI is intentionally minimal; before adding new checks (linting, type-checking, or tests), verify they integrate cleanly with `requirements.txt` and the existing GitHub Actions workflows.
- When adding tests, prefer to keep them compatible with a plain `pytest` invocation so they can later be slotted into the `ci.yml` workflow easily.

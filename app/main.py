from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from loguru import logger
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import settings
from .routes import auth as auth_routes
from .routes import views as view_routes
from .routes import api as api_routes

app = FastAPI(title="Fullstack GCP App", version="0.1.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


from .db import Base, engine  # noqa: E402


@app.on_event("startup")
async def on_startup() -> None:
    """Application startup hook.

    We try to auto-create DB tables for convenience in dev. In Cloud Run, a
    transient or misconfigured DATABASE_URL should not prevent the container
    from starting, so we log errors instead of crashing the process.
    """

    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:  # noqa: BLE001
        logger.error("Error creating database tables on startup: {}", exc)


@app.get("/healthz", tags=["health"])
async def healthcheck() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, tags=["views"])
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# Include routers
app.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
app.include_router(view_routes.router, tags=["views"])
app.include_router(api_routes.router, prefix="/api", tags=["api"])

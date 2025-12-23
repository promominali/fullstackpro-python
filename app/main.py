from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
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
    # For simplicity we auto-create tables; in production consider Alembic migrations instead.
    Base.metadata.create_all(bind=engine)


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

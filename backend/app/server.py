import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config.database import ensure_indexes

# CORS origins come from the CORS_ORIGINS env var (comma-separated list),
# falling back to the local development origins.
def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [o.strip() for o in raw.split(",") if o.strip()]


_DEFAULT_DIST = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)
FRONTEND_DIST = os.getenv("FRONTEND_DIST", _DEFAULT_DIST)


@asynccontextmanager
async def lifespan(app):
    ensure_indexes()
    yield


app = FastAPI(title="Attendance Planner API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}


def _serve_frontend():
    """If a built frontend exists, host the API and the React app from ONE
    origin. API routes (registered above) always take precedence; every other
    GET path falls through to the frontend, so SPA deep-links work on refresh.
    """
    if not os.path.isdir(FRONTEND_DIST):
        return

    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    index_file = os.path.join(FRONTEND_DIST, "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_catch_all(full_path: str):
        if full_path:
            candidate = os.path.normpath(os.path.join(FRONTEND_DIST, full_path))
            # Guard against path traversal outside the dist directory.
            if (
                os.path.commonpath([FRONTEND_DIST, candidate]) == FRONTEND_DIST
                and os.path.isfile(candidate)
            ):
                return FileResponse(candidate)
        return FileResponse(index_file)


_serve_frontend()

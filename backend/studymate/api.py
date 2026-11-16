"""Application factory: wires settings, database, workers, routers and the SPA."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import RateLimiter
from .config import ROOT, Settings
from .db import Database
from .events import TicketStore
from .routes import (
    account,
    admin,
    auth,
    bookings,
    calendar,
    chat,
    discover,
    events,
    mentor,
    public,
    quiz,
)
from .seed import seed
from .service import fail

DIST = ROOT / "frontend" / "dist"

# Everything is served from this origin; external meeting links are opened as
# ordinary navigations, which CSP does not restrict.
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    database = Database(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.bus.bind(asyncio.get_running_loop())
        database.migrate()
        seed(database)
        task = None
        if settings.worker_enabled:
            from .inbox import run_workers

            task = asyncio.create_task(run_workers(database))
        app.state.worker_task = task
        yield
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        database.engine.dispose()

    app = FastAPI(title="StudyMate Campus", version="2.2.0", lifespan=lifespan)
    app.state.db = database
    app.state.settings = settings
    app.state.worker_task = None
    app.state.rate_limiter = RateLimiter()
    app.state.chat_limiter = RateLimiter(per_account=20, per_client=10**6)
    app.state.tickets = TicketStore()
    app.state.heartbeat_seconds = 15.0

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path in ("/docs", "/redoc"):
            pass  # Swagger UI loads its own CDN assets; keep it usable locally.
        else:
            response.headers["Content-Security-Policy"] = CSP
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    for module in (
        auth,
        public,
        account,
        discover,
        mentor,
        bookings,
        chat,
        calendar,
        quiz,
        admin,
        events,
    ):
        app.include_router(module.router)

    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")
    if (DIST / "images").exists():
        app.mount("/images", StaticFiles(directory=DIST / "images"), name="images")

    @app.get("/", include_in_schema=False)
    @app.get("/{website_path:path}", include_in_schema=False)
    def index(website_path: str = ""):
        if website_path == "api" or website_path.startswith("api/"):
            fail(404, "Маршрут не найден")
        if not (DIST / "index.html").exists():
            return JSONResponse(
                {"detail": "Сначала соберите интерфейс: cd frontend && npm ci && npm run build"},
                status_code=503,
            )
        return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})

    return app

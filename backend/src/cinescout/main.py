"""FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqladmin import Admin

from cinescout.admin.auth import AdminAuth
from cinescout.admin.views import (
    CinemaAdmin,
    FilmAdmin,
    FilmAliasAdmin,
    PasswordChangeView,
    ScrapeToolsView,
    ShowingAdmin,
)
from cinescout.api.routes import admin, cinemas, films, health, showings
from cinescout.config import settings
from cinescout.database import engine
from cinescout.tasks.scrape_job import run_scrape_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: configure and start the scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_scrape_all,
        trigger=CronTrigger(day_of_week="wed", hour=3, minute=0),
        id="weekly_scrape",
        name="Weekly scrape of all cinemas",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — weekly scrape registered for every Wednesday at 03:00")

    # Fire a one-off startup scrape in the background
    asyncio.create_task(run_scrape_all())
    logger.info("Startup scrape triggered in background")

    yield

    # Shutdown: stop the scheduler gracefully
    scheduler.shutdown(wait=False)
    logger.info("Scheduler shut down")


# Create FastAPI app
app = FastAPI(
    title="CineScout API",
    description="Film showing aggregator for London cinemas",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://cinescout-web.fly.dev",  # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(cinemas.router, prefix="/api", tags=["cinemas"])
app.include_router(films.router, prefix="/api", tags=["films"])
app.include_router(showings.router, prefix="/api", tags=["showings"])
app.include_router(admin.router, prefix="/api", tags=["admin"])

# Setup SQLAdmin
auth_backend = AdminAuth(secret_key=settings.admin_secret_key)
admin_panel = Admin(app, engine, authentication_backend=auth_backend, title="CineScout Admin")
for view in [CinemaAdmin, FilmAdmin, ShowingAdmin, FilmAliasAdmin, ScrapeToolsView, PasswordChangeView]:
    admin_panel.add_view(view)

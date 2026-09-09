"""Admin FastAPI application."""

from fastapi import FastAPI
from sqladmin import Admin

from cinescout.admin.auth import AdminAuth
from cinescout.admin.views import (
    CinemaAdmin,
    FilmAdmin,
    FilmAliasAdmin,
    PasswordChangeView,
    ScrapeToolsView,
    ShowingAdmin,
    UserAdmin,
    WatchLogAdmin,
)
from cinescout.config import settings
from cinescout.database import engine


def create_admin_app() -> FastAPI:
    app = FastAPI(title="CineScout Admin")
    auth = AdminAuth(secret_key=settings.admin_secret_key)
    admin = Admin(app, engine, authentication_backend=auth, title="CineScout Admin")
    for view in [
        CinemaAdmin,
        FilmAdmin,
        ShowingAdmin,
        FilmAliasAdmin,
        UserAdmin,
        WatchLogAdmin,
        ScrapeToolsView,
        PasswordChangeView,
    ]:
        admin.add_view(view)
    return app


admin_app = create_admin_app()

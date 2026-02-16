"""SQLAdmin authentication backend."""

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from cinescout.config import settings


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        ok = (
            form.get("username") == settings.admin_username
            and form.get("password") == settings.admin_password
        )
        if ok:
            request.session.update({"authenticated": True})
        return ok

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("authenticated", False)

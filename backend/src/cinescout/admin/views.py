"""SQLAdmin model and tool views."""

import asyncio
from datetime import date

from sqladmin import BaseView, ModelView, expose
from starlette.requests import Request
from starlette.responses import HTMLResponse

from cinescout.models.cinema import Cinema
from cinescout.models.film import Film
from cinescout.models.film_alias import FilmAlias
from cinescout.models.showing import Showing
from cinescout.scripts.backfill_tmdb import backfill
from cinescout.scripts.smoke_test import run_smoke_test, SmokeTestReport
from cinescout.config import settings
from cinescout.tasks.scrape_job import run_scrape_all, run_scrape_selected


class CinemaAdmin(ModelView, model=Cinema):
    column_list = [
        Cinema.id,
        Cinema.name,
        Cinema.city,
        Cinema.address,
        Cinema.scraper_type,
        Cinema.has_online_booking,
    ]
    column_searchable_list = [Cinema.name, Cinema.city]
    column_sortable_list = [Cinema.name, Cinema.city]


class FilmAdmin(ModelView, model=Film):
    column_list = [
        Film.id,
        Film.title,
        Film.year,
        Film.directors,
        Film.countries,
        Film.tmdb_id,
    ]
    column_searchable_list = [Film.title]
    column_sortable_list = [Film.title, Film.year]


class ShowingAdmin(ModelView, model=Showing):
    column_list = [
        Showing.id,
        Showing.cinema_id,
        Showing.film_id,
        Showing.start_time,
        Showing.screen_name,
        Showing.format_tags,
        Showing.price,
    ]
    column_searchable_list = [Showing.cinema_id, Showing.film_id]
    can_create = False
    can_edit = False


class FilmAliasAdmin(ModelView, model=FilmAlias):
    column_list = [FilmAlias.id, FilmAlias.normalized_title, FilmAlias.film_id]
    column_searchable_list = [FilmAlias.normalized_title]


_TOOLS_TEMPLATE = """\
{% extends "sqladmin/layout.html" %}
{% block content %}
<div class="container-fluid p-4">
  <h2>Scrape Tools</h2>
  <form method="post" class="mt-3 d-flex align-items-center gap-2 flex-wrap">
    <button name="action" value="scrape" class="btn btn-primary">Trigger Scrape</button>
    <button name="action" value="backfill" class="btn btn-secondary">Trigger Backfill</button>
  </form>

  <hr class="my-4">

  <h2>Admin</h2>
  <a href="/admin/password" class="btn btn-outline-secondary mt-2">Change Password</a>
  {% if message %}
  <div class="alert alert-success mt-3">{{ message }}</div>
  {% endif %}

  <hr class="my-4">

  <h2>Smoke Test</h2>
  <form method="post" class="mt-3 d-flex align-items-center gap-2 flex-wrap">
    <input type="date" name="smoke_date" value="{{ today }}" class="form-control" style="width:auto">
    <input type="number" name="min_showings" value="1" min="0" class="form-control" style="width:90px" title="Min showings">
    <button name="action" value="smoke_test" class="btn btn-outline-dark">Run Smoke Test</button>
  </form>

  {% if smoke_report %}
  <div class="mt-4">
    <h5>
      Results for {{ smoke_report.check_date }}
      {% if smoke_report.all_ok %}
        <span class="badge bg-success ms-2">All OK</span>
      {% else %}
        <span class="badge bg-danger ms-2">Issues found</span>
      {% endif %}
    </h5>
    <form method="post">
      <table class="table table-sm table-bordered mt-2" style="max-width:580px">
        <thead>
          <tr>
            <th style="width:36px">
              <input type="checkbox" id="select-all" title="Select all" checked>
            </th>
            <th></th>
            <th>Cinema</th>
            <th class="text-end">Showings</th>
          </tr>
        </thead>
        <tbody>
        {% for r in smoke_report.results %}
          <tr class="{{ 'table-danger' if not r.ok else '' }}">
            <td>
              <input type="checkbox" name="cinema_ids" value="{{ r.id }}"
                     {{ 'checked' if not r.ok else '' }}>
            </td>
            <td>{{ '✓' if r.ok else '✗' }}</td>
            <td>{{ r.name }}</td>
            <td class="text-end">{{ r.count }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
      <button name="action" value="scrape_selected" class="btn btn-warning">
        Scrape Selected
      </button>
    </form>
  </div>
  {% endif %}
  <script>
    document.getElementById('select-all')?.addEventListener('change', function() {
      document.querySelectorAll('input[name="cinema_ids"]').forEach(cb => cb.checked = this.checked);
    });
  </script>
</div>
{% endblock %}
"""


class ScrapeToolsView(BaseView):
    name = "Tools"
    icon = "fa-wrench"

    @expose("/tools", methods=["GET", "POST"])
    async def tools(self, request: Request) -> HTMLResponse:
        message: str | None = None
        smoke_report: SmokeTestReport | None = None

        if request.method == "POST":
            form = await request.form()
            action = form.get("action")
            if action == "scrape":
                asyncio.create_task(run_scrape_all())
                message = "Scrape started in background."
            elif action == "backfill":
                asyncio.create_task(backfill())
                message = "Backfill started in background."
            elif action == "scrape_selected":
                cinema_ids = list(form.getlist("cinema_ids"))
                if cinema_ids:
                    asyncio.create_task(run_scrape_selected(cinema_ids))
                    message = f"Scraping {len(cinema_ids)} cinema(s) in background."
                else:
                    message = "No cinemas selected."
            elif action == "smoke_test":
                raw_date = form.get("smoke_date") or str(date.today())
                min_showings = int(form.get("min_showings") or 1)
                check_date = date.fromisoformat(str(raw_date))
                smoke_report = await run_smoke_test(check_date, min_showings)

        tmpl = self.templates.env.from_string(_TOOLS_TEMPLATE)
        content = await tmpl.render_async(
            request=request,
            message=message,
            smoke_report=smoke_report,
            today=str(date.today()),
        )
        return HTMLResponse(content)


_PASSWORD_CHANGE_TEMPLATE = """\
{% extends "sqladmin/layout.html" %}
{% block content %}
<div class="container-fluid p-4">
  <h2>Change Admin Password</h2>

  <div class="alert alert-warning mt-3">
    <strong>Note:</strong> Password changes are temporary and only apply to the current session.
    <br>For persistent changes:
    <ul class="mb-0 mt-2">
      <li><strong>Local:</strong> Update <code>ADMIN_PASSWORD</code> in <code>backend/.env</code></li>
      <li><strong>Fly.io:</strong> Run <code>flyctl secrets set ADMIN_PASSWORD=new_password</code></li>
    </ul>
  </div>

  <form method="post" class="mt-4" style="max-width: 400px;">
    <div class="mb-3">
      <label for="current_password" class="form-label">Current Password</label>
      <input type="password" class="form-control" id="current_password" name="current_password" required>
    </div>
    <div class="mb-3">
      <label for="new_password" class="form-label">New Password</label>
      <input type="password" class="form-control" id="new_password" name="new_password" required minlength="8">
      <div class="form-text">Minimum 8 characters</div>
    </div>
    <div class="mb-3">
      <label for="confirm_password" class="form-label">Confirm New Password</label>
      <input type="password" class="form-control" id="confirm_password" name="confirm_password" required>
    </div>
    <button type="submit" class="btn btn-primary">Change Password</button>
  </form>

  {% if error %}
  <div class="alert alert-danger mt-3">{{ error }}</div>
  {% endif %}
  {% if success %}
  <div class="alert alert-success mt-3">{{ success }}</div>
  {% endif %}
</div>
{% endblock %}
"""


class PasswordChangeView(BaseView):
    name = "Change Password"
    icon = "fa-key"

    @expose("/password", methods=["GET", "POST"])
    async def change_password(self, request: Request) -> HTMLResponse:
        error: str | None = None
        success: str | None = None

        if request.method == "POST":
            form = await request.form()
            current_password = form.get("current_password")
            new_password = form.get("new_password")
            confirm_password = form.get("confirm_password")

            # Validate current password
            if current_password != settings.admin_password:
                error = "Current password is incorrect"
            # Validate new password
            elif not new_password or len(str(new_password)) < 8:
                error = "New password must be at least 8 characters long"
            # Validate confirmation
            elif new_password != confirm_password:
                error = "New passwords do not match"
            else:
                # Update password in settings (runtime only)
                settings.admin_password = str(new_password)
                success = "Password changed successfully (current session only)"

        tmpl = self.templates.env.from_string(_PASSWORD_CHANGE_TEMPLATE)
        content = await tmpl.render_async(
            request=request,
            error=error,
            success=success,
        )
        return HTMLResponse(content)

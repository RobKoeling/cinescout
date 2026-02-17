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
from cinescout.tasks.scrape_job import run_scrape_all


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
    column_searchable_list = [Showing.cinema_id]
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
    <table class="table table-sm table-bordered mt-2" style="max-width:520px">
      <thead><tr><th></th><th>Cinema</th><th class="text-end">Showings</th></tr></thead>
      <tbody>
      {% for r in smoke_report.results %}
        <tr class="{{ 'table-danger' if not r.ok else '' }}">
          <td>{{ '✓' if r.ok else '✗' }}</td>
          <td>{{ r.name }}</td>
          <td class="text-end">{{ r.count }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}
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

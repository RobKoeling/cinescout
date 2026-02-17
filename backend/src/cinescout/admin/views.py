"""SQLAdmin model and tool views."""

import asyncio

from sqladmin import BaseView, ModelView, expose
from starlette.requests import Request
from starlette.responses import HTMLResponse

from cinescout.models.cinema import Cinema
from cinescout.models.film import Film
from cinescout.models.film_alias import FilmAlias
from cinescout.models.showing import Showing
from cinescout.scripts.backfill_tmdb import backfill
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
{% extends "layout.html" %}
{% block content %}
<div class="container-fluid p-4">
  <h2>Scrape Tools</h2>
  <form method="post" class="mt-3">
    <button name="action" value="scrape" class="btn btn-primary me-2">
      Trigger Scrape
    </button>
    <button name="action" value="backfill" class="btn btn-secondary">
      Trigger Backfill
    </button>
  </form>
  {% if message %}
  <div class="alert alert-success mt-3">{{ message }}</div>
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
        if request.method == "POST":
            form = await request.form()
            action = form.get("action")
            if action == "scrape":
                asyncio.create_task(run_scrape_all())
                message = "Scrape started in background."
            elif action == "backfill":
                asyncio.create_task(backfill())
                message = "Backfill started in background."

        tmpl = self.templates.env.from_string(_TOOLS_TEMPLATE)
        content = tmpl.render(request=request, message=message)
        return HTMLResponse(content)

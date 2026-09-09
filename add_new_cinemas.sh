#!/usr/bin/env bash
# Seed and scrape the three new cinemas: Close-Up, Phoenix, Coldharbour Blue.
set -e

cd "$(dirname "$0")/backend"
source .venv/bin/activate

echo "Seeding new cinemas into the database..."
python -m cinescout.scripts.seed_cinemas

echo "Scraping new cinemas..."
python -c "
import asyncio
from cinescout.tasks.scrape_job import run_scrape_selected
asyncio.run(run_scrape_selected(['close-up', 'phoenix-east-finchley', 'coldharbour-blue']))
"

echo "Done."

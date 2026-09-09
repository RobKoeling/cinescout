# Install / sync dependencies (after pulling changes etc.)
cd backend && uv sync --extra dev --system-certs

# Activate venv (same as before)
echo Now activate venv: source backend/.venv/bin/activate

# Run anything — pytest, uvicorn, alembic — unchanged

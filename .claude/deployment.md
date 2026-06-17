# Deployment

CineScout runs on Fly.io. Two apps: `cinescout-api` (backend) and `cinescout-web` (frontend).
Active database: `cinescout-db-v2` (Postgres 17, region `lhr`).

## Before deploying — always confirm

```bash
pwd          # must be the project backend/ directory, not a worktree copy
git status   # confirm you're on the right branch with the right changes
```

Deploy **from the main repo**, not from a worktree copy:
```
/Users/koelingr/PycharmProjects/ClaudeCode/cinescout/backend
```

Pull latest before deploying if you've been working in a worktree:
```bash
cd /path/to/cinescout/backend
git pull origin main
fly deploy --local-only
```

## Deploy commands

```bash
# Backend (from backend/)
fly deploy --local-only

# Force full rebuild (clears Docker layer cache — use when code changes seem ignored)
fly deploy --local-only --no-cache

# Push a secret
fly secrets set KEY=value -a cinescout-api

# Refresh Curzon auth token (run from local machine, not Fly)
cd backend && python -m cinescout.scripts.refresh_curzon_token
```

## Fly.io config highlights (`backend/fly.toml`)

- `min_machines_running = 1` — keeps one machine alive so scrapes aren't killed mid-run
- `auto_stop_machines = 'stop'` — still stops idle machines, but never below 1
- Release command: `alembic upgrade head` — migrations run automatically on deploy

## Known production issues

| Issue | Status | Notes |
|---|---|---|
| Curzon 403 from Fly.io IPs | Workaround | Use `CURZON_AUTH_TOKEN` secret; refresh every ~10 h |
| BFI Playwright on Fly | Flaky | Cloudflare challenge sometimes blocks headless browser |
| DB connection errors after idle | Fixed | `pool_pre_ping=True` + `pool_recycle=300` in `database.py` |

## Secrets managed on Fly

```
ADMIN_PASSWORD, ADMIN_SECRET_KEY, ADMIN_USERNAME
DATABASE_URL
TMDB_API_KEY
CURZON_AUTH_TOKEN   ← expires every 12 h; refresh manually
```

## Monitoring

```bash
fly logs -a cinescout-api          # live logs
fly status -a cinescout-api        # machine health
fly secrets list -a cinescout-api  # confirm secrets are deployed
```

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

# Force full rebuild (clears container layer cache — use when code changes seem ignored)
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

## Podman and `fly deploy --local-only`

Local builds use Podman via its Docker-compatible API socket. Podman lives in
`/opt/podman/bin` (not on the default PATH). Before deploying:

```bash
export PATH=/opt/podman/bin:$PATH
podman machine start
export DOCKER_HOST="unix://$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}')"
fly deploy --local-only
```

The `Dockerfile`s are plain OCI build files and work unchanged with Podman.

### One-time Podman VM setup (redo if the VM is recreated with `podman machine init`)

Two problems showed up on this corporate Mac, both fixed inside the VM:

1. **"insufficient UIDs or GIDs available in user namespace"** — flyctl uploads the
   build context owned by the macOS user/group IDs (very large numbers), which exceed
   the VM's default 1,000,000-ID range. Widen it, starting *above* the user's own UID
   (the range may not include it):
   ```bash
   podman machine ssh 'sudo sed -i "s/^core:100000:1000000$/core:300000000:2000000000/" /etc/subuid /etc/subgid && podman system migrate'
   podman machine stop && podman machine start
   podman machine ssh 'systemctl --user restart podman.socket'
   ```
2. **Image push to registry.fly.io dies mid-upload** ("broken pipe" / "app repository
   not found") — the Zscaler TLS proxy. Trust its CA inside the VM:
   ```bash
   B=$(base64 < backend/certs/zscaler-bundle.crt | tr -d '\n')
   podman machine ssh "echo $B | base64 -d | sudo tee /etc/pki/ca-trust/source/anchors/zscaler-bundle.crt >/dev/null && sudo update-ca-trust && systemctl --user restart podman.socket"
   ```

**Side effect of changing the subuid/subgid range:** files in existing Podman volumes
and cached images are owned by the *old* mapped IDs, so after a change the local
Postgres container can fail with "permission denied" (e.g. on `/var/run/postgresql`
or the data dir). Fix: re-own the volume's `_data` directory inside the VM to the
new mapped postgres ID (here `300000069:300000069`), remove the old containers and
cached images, then recreate with `podman compose up -d`. Data is preserved.

If flyctl says "docker is unavailable", the VM's API socket is down: run
`podman machine ssh 'systemctl --user restart podman.socket'`.
`fly deploy --remote-only` does not work on this network (Depot builder TLS resets).

## Local containers after a reboot

Containers (`cinescout-db-1`, `cinescout-redis-1`) survive a reboot but are stopped,
and nothing restarts them. With the Podman machine running:

```bash
/opt/podman/bin/podman start cinescout-db-1 cinescout-redis-1
```

`podman compose` delegates to an external `docker-compose`/`podman-compose`; it stops
working if neither is installed (it broke when Docker was removed). `podman start`
needs no compose tool.

If `podman ps` says "Cannot connect to Podman ... ssh: rejected" (and Podman Desktop
shows no containers) while `podman machine list` says the VM is running, the VM's API
socket is down. Restart it:

```bash
podman machine ssh 'systemctl --user restart podman.socket'
```

If that prints `configure storage: overlay: recover stale temp dirs ... operation not
permitted`, remove the stale directory it names as root (it lives under
`~/.local/share/containers/storage/overlay/tempdirs/` in the VM — leftover layer
extractions, not volumes), then restart the socket again:

```bash
podman machine ssh 'sudo rm -rf ~/.local/share/containers/storage/overlay/tempdirs/temp-dir-*; systemctl --user restart podman.socket'
```

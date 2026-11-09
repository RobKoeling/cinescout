#!/usr/bin/env bash
# Make sure the local Postgres + Redis containers (Podman) are up.
# Safe to run repeatedly: does nothing if everything is already running.
# Used by dev.sh and daily_workflow.sh.

set -u

export PATH=/opt/podman/bin:$PATH
ROOT="$(cd "$(dirname "$0")" && pwd)"
CONTAINERS=(cinescout-db-1 cinescout-redis-1)

if ! command -v podman >/dev/null 2>&1; then
  echo "podman not found (expected in /opt/podman/bin)" >&2
  exit 1
fi

# 1. Podman machine (macOS VM)
if ! podman machine list --format '{{.Running}}' 2>/dev/null | grep -q true; then
  echo "Starting Podman machine..."
  podman machine start || exit 1
fi

# 2. API socket: after a reboot the VM can be up while its socket is down
if ! podman info >/dev/null 2>&1; then
  echo "Podman API socket down, restarting it..."
  podman machine ssh 'systemctl --user restart podman.socket' >/dev/null 2>&1
  sleep 3
fi
if ! podman info >/dev/null 2>&1; then
  echo "Cannot connect to Podman. See .claude/deployment.md ('Local containers after a reboot')." >&2
  exit 1
fi

# 3. Containers: start existing ones, or create them on first run
if podman container exists "${CONTAINERS[0]}" && podman container exists "${CONTAINERS[1]}"; then
  podman start "${CONTAINERS[@]}" >/dev/null || exit 1
else
  echo "Containers not found, creating them with podman compose..."
  (cd "$ROOT" && podman compose up -d) || exit 1
fi

# 4. Wait for Postgres to be ready (up to ~60 s)
for _ in $(seq 1 30); do
  if podman exec cinescout-db-1 pg_isready -U postgres >/dev/null 2>&1; then
    echo "Postgres and Redis are up."
    exit 0
  fi
  sleep 2
done
echo "Postgres did not become ready in time. Check: podman logs cinescout-db-1" >&2
exit 1

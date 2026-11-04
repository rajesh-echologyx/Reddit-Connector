#!/bin/sh
set -eu

host="${DB_HOST:-db}"
port="${DB_PORT:-5432}"
retries="${DB_WAIT_RETRIES:-30}"

echo "Waiting for Postgres at ${host}:${port}..."
i=0
while [ "$i" -lt "$retries" ]; do
  if python - <<PY
import socket, sys
s = socket.socket()
s.settimeout(1)
try:
    s.connect(("${host}", int("${port}")))
except Exception:
    sys.exit(1)
finally:
    s.close()
PY
  then
    echo "Postgres is reachable."
    exit 0
  fi
  i=$((i + 1))
  sleep 1
done

echo "Timed out waiting for Postgres." >&2
exit 1

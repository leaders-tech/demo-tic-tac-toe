#!/bin/sh
# This script runs Docker Compose with whichever compose command is available.
# Edit this file when Docker Compose command detection or shared compose flags change.
# Copy the helper pattern here when you add another small Docker wrapper script.

set -eu

if docker compose version >/dev/null 2>&1; then
  exec docker compose "$@"
fi

if command -v docker-compose >/dev/null 2>&1; then
  exec docker-compose "$@"
fi

printf '%s\n' "Docker Compose is not available. Install 'docker compose' or 'docker-compose'." >&2
exit 1

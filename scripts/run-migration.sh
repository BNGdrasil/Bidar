#!/usr/bin/env bash
# Database migration runner for the Bidar auth server.
#
# The production database is the host PostgreSQL instance on VM3, database
# `bngdrasil`. There is no PostgreSQL container involved.
#
# Run this ON VM3, as a user allowed to sudo to postgres:
#   ./scripts/run-migration.sh migrations/002_align_role_and_superuser.sql
#
# Or from a workstation that can reach VM3 over SSH:
#   scp migrations/002_align_role_and_superuser.sql ubuntu@<VM3_HOST>:/tmp/
#   ssh ubuntu@<VM3_HOST> 'sudo -u postgres psql -d bngdrasil \
#       -v ON_ERROR_STOP=1 -f /tmp/002_align_role_and_superuser.sql'

set -euo pipefail

MIGRATION_FILE=${1:-}
DB_NAME=${DB_NAME:-bngdrasil}

if [ -z "$MIGRATION_FILE" ]; then
    echo "Usage: $0 <migration-file.sql>" >&2
    echo "Available migrations:" >&2
    ls -1 "$(dirname "$0")/../migrations"/*.sql >&2
    exit 2
fi

if [ ! -f "$MIGRATION_FILE" ]; then
    echo "Migration file not found: $MIGRATION_FILE" >&2
    exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
    echo "psql not found. Run this on the database host (VM3)." >&2
    exit 1
fi

echo "Database : $DB_NAME"
echo "Migration: $MIGRATION_FILE"

# ON_ERROR_STOP=1 makes psql exit non-zero on the first failing statement so
# that a broken migration cannot be reported as a success.
sudo -u postgres psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$MIGRATION_FILE"

echo "Migration applied. Verify with:"
echo "  sudo -u postgres psql -d ${DB_NAME} -c '\\d users'"
echo "  sudo -u postgres psql -d ${DB_NAME} -c \"SELECT role, is_superuser, COUNT(*) FROM users GROUP BY 1, 2 ORDER BY 1;\""

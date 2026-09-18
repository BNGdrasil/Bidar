#!/bin/bash

set -e

echo "🧪 Running Bidar tests..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: This script must be run from the auth-server directory"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    uv sync
fi

# Run tests with coverage.
# The test environment is set explicitly so that a stray DEBUG/ENVIRONMENT in
# the parent shell or a local .env cannot change what is under test.
echo "🔍 Running tests with coverage..."
ENVIRONMENT=test \
DEBUG=false \
DATABASE_URL=sqlite+aiosqlite:///:memory: \
JWT_SECRET_KEY=bidar-local-test-signing-key-not-for-production \
ALLOWED_HOSTS='*' \
uv run pytest tests/ \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=xml \
    -v

echo "✅ Tests completed successfully!"
echo "📊 Coverage report generated in htmlcov/index.html"

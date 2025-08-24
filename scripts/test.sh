#!/bin/bash
# --------------------------------------------------------------------------
# Auth Server 테스트 실행 스크립트
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------

set -e

echo "🧪 Running Auth Server tests..."

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

# Run tests with coverage
echo "🔍 Running tests with coverage..."
uv run pytest tests/ \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=xml \
    -v

echo "✅ Tests completed successfully!"
echo "📊 Coverage report generated in htmlcov/index.html"

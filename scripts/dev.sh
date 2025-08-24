#!/bin/bash

# Auth Server 개발 서버 실행 스크립트

echo "🔐 Starting Auth Server development server..."

# 현재 디렉토리가 auth-server인지 확인
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: This script must be run from the auth-server directory"
    exit 1
fi

# 가상환경이 없으면 생성
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    uv sync
fi

# 환경 변수 파일 확인
if [ ! -f ".env" ]; then
    if [ -f "env.example" ]; then
        echo "📝 Creating .env file from env.example..."
        cp env.example .env
        echo "⚠️  Please edit .env file with your configuration"
    else
        echo "⚠️  No .env file found. Please create one manually."
    fi
fi

# 개발 서버 실행
echo "🌐 Starting development server on http://localhost:8001"
echo "📚 API documentation: http://localhost:8001/docs"
echo "🔍 Health check: http://localhost:8001/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8001

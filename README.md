<p align="center">
    <img align="top" width="30%" src="https://github.com/BNGdrasil/BNGdrasil/blob/main/images/Bidar.png" alt="Bidar"/>
</p>

<div align="center">

# 🔐 Bidar (bnbong + Vidar)

**Centralized Authentication Server for BNGdrasil Ecosystem**

[![Python](https://img.shields.io/badge/Python-3.12+-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/Tests-85%20Passed-green.svg?style=flat-square)](tests/)
[![Code Style](https://img.shields.io/badge/Code%20Style-Black-black.svg?style=flat-square)](https://github.com/psf/black)

*Part of the [BNGdrasil](https://github.com/BNGdrasil/BNGdrasil) ecosystem - Building a personal cloud nation*

</div>

---

## Overview

**Bidar** is the centralized authentication server for the BNGdrasil ecosystem, providing secure JWT-based authentication and user management services. Named after the Norse god Vidar, it serves as the guardian of identity and access control across all microservices in your personal cloud infrastructure.

As a core component of the BNGdrasil project, Bidar seamlessly integrates with **Bifrost** (API Gateway), **Bantheon** (Portfolio/Admin UI), and other services to provide unified authentication across the entire ecosystem.

## Key Features

- **JWT Authentication**: Secure token-based auth with access/refresh tokens
- **User Management**: Registration, profile management, and admin controls
- **Security**: bcrypt password hashing, Redis session management, CORS protection
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation

## Architecture

Bidar is designed as a microservice within the BNGdrasil ecosystem:

```mermaid
graph LR
    A["🌐 Cloudflare"] --> B["🔀 Nginx Proxy"]
    B --> C["🌉 Bifrost<br/>(API Gateway)"]
    C --> D["🔐 Bidar<br/>(Auth Server)"]
    D --> E["🗄️ PostgreSQL<br/>(Database)"]
    D --> F["🔄 Redis<br/>(Cache/Sessions)"]

    style A fill:#f96,stroke:#333,stroke-width:2px
    style C fill:#4a9,stroke:#333,stroke-width:2px
    style D fill:#49a,stroke:#333,stroke-width:2px
    style E fill:#94a,stroke:#333,stroke-width:2px
    style F fill:#a49,stroke:#333,stroke-width:2px
```

## Tech Stack

- **Framework**: FastAPI 0.104.1
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **Authentication**: JWT (python-jose)
- **Password Hashing**: bcrypt (passlib)
- **ORM**: SQLModel (SQLAlchemy 2.0)
- **Testing**: pytest with async support
- **Code Quality**: black, isort, flake8, mypy
- **Package Manager**: uv

## Prerequisites

- **Python 3.12+**
- **Docker**
- **Redis**
- **PostgreSQL**

## Installation & Start

```bash
# Clone the repository
git clone git@github.com:BNGdrasil/Bidar.git
cd Bidar

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies and create virtual environment
uv sync

# Copy environment template
cp env.example .env

# Edit the .env file with your configuration
# ⚠️ Important: Change JWT_SECRET_KEY in production

# After environment & Database setup
uv run python -m src.main

# Or using development script
./scripts/dev.sh

# Server will start at http://localhost:8001
```

**Essential Environment Variables:**

```env
# Security (CHANGE IN PRODUCTION!)
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
ALLOWED_HOSTS=*
ALLOWED_ORIGINS=*

# Database
DATABASE_URL=postgresql://bnbong:password@postgres:5432/bnbong

# Redis
REDIS_URL=redis://redis:6379/1

# Server
HOST=0.0.0.0
PORT=8001
ENVIRONMENT=development
```

### Database Setup

Start PostgreSQL and Redis services. Using Docker:

```bash
# Start PostgreSQL
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=bnbong \
  -e POSTGRES_USER=bnbong \
  -p 5432:5432 \
  postgres:15

# Start Redis
docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine

# Or use Docker Compose (recommended)
docker compose up -d postgres redis
```

### Verify Installation

```bash
# Health check
curl http://localhost:8001/health

# API documentation
open http://localhost:8001/docs
```

## API Endpoints

### Authentication

```http
POST /auth/token      # Login (OAuth2 compatible)
POST /auth/refresh    # Refresh access token
GET  /auth/me         # Get current user info
```

### User Management

```http
POST /users/register           # User registration
GET  /users/users             # List all users (superuser only)
PUT  /users/{id}/activate     # Activate user (superuser only)
PUT  /users/{id}/deactivate   # Deactivate user (superuser only)
```

### Health & Monitoring

```http
GET  /health          # Service health check
GET  /               # Service information
```

### Request Examples

**User Registration:**

```bash
curl -X POST "http://localhost:8001/users/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "securepassword123",
    "full_name": "John Doe"
  }'
```

**Login:**

```bash
curl -X POST "http://localhost:8001/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=johndoe&password=securepassword123"
```

**Access Protected Endpoint:**

```bash
curl -X GET "http://localhost:8001/auth/me" \
  -H "Authorization: Bearer <your-access-token>"
```

## Docker Deployment

Bidar uses docker for deployment:

```bash
# Build Docker image
docker build -t bidar-auth-server .

# Run container with environment file
docker run -p 8001:8001 --env-file .env bidar-auth-server

# Or use Docker Compose (recommended for development)
docker compose up -d
```

## Security

### Essential Security Checklist

**Critical (Change Before Production):**

```env
# Generate a strong secret key (32+ characters)
JWT_SECRET_KEY=<generate-strong-random-key>

# Restrict hosts and origins
ALLOWED_HOSTS=your-domain.com,api.your-domain.com
ALLOWED_ORIGINS=https://your-frontend.com

# Use production database
DATABASE_URL=postgresql://user:password@db-host:5432/bidar_prod

# Use production Redis
REDIS_URL=redis://redis-host:6379/0
```

**Recommended:**

- Enable HTTPS/TLS termination at reverse proxy
- Set up proper logging and monitoring
- Configure backup strategies for PostgreSQL
- Implement Redis persistence configuration
- Set up rate limiting at Bifrost gateway level

---

## BNGdrasil Ecosystem

Bifrost is part of the larger **[BNGdrasil](https://github.com/BNGdrasil)** cloud infrastructure project:

- **🔐 [Bidar](https://github.com/BNGdrasil/Bidar)** - Authentication & Authorization Server (this project)
- **🌉 [Bifrost](https://github.com/BNGdrasil/Bifrost)** - API Gateway
- **🏗️ [Baedalus](https://github.com/BNGdrasil/Baedalus)** - Infrastructure as Code (Terraform)
- **🌐 [Bsgard](https://github.com/BNGdrasil/Bsgard)** - Custom VPC & Networking
- **🎨 [Bantheon](https://github.com/BNGdrasil/Bantheon)** - Web Frontend & Portfolio
- **🎮 [Blysium](https://github.com/BNGdrasil/Blysium)** - Gaming Platform

Each component is designed to work independently while integrating seamlessly with others.

---

## License

This project is part of the BNGdrasil personal cloud infrastructure project.
For educational and personal development purposes.

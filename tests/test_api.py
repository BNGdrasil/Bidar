# --------------------------------------------------------------------------
# Tests for API endpoints
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import pytest
import pytest_asyncio  # type: ignore
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_password_hash
from src.models.user import User


class TestAPIEndpoints:
    """Test cases for API endpoints."""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user for API tests."""
        user = User(
            username="apiuser",
            email="api@example.com",
            hashed_password=get_password_hash("apipassword123"),
            full_name="API Test User",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    def test_health_check(self, client: TestClient) -> None:
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "auth-server"

    def test_root_endpoint(self, client: TestClient) -> None:
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Welcome to Auth Server"
        assert data["version"] == "1.0.0"
        assert "docs" in data

    def test_register_user_success(self, client: TestClient) -> None:
        """Test successful user registration via API."""
        user_data = {
            "username": "newapiuser",
            "email": "newapi@example.com",
            "password": "newapipassword123",
            "full_name": "New API User",
        }

        response = client.post("/users/register", json=user_data)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "User registered successfully"
        assert "user_id" in data
        assert data["username"] == user_data["username"]
        assert data["email"] == user_data["email"]

    def test_login_success(self, client: TestClient, test_user: User) -> None:
        """Test successful login via API."""
        login_data = {
            "username": test_user.username,
            "password": "apipassword123",
        }

        response = client.post("/auth/token", data=login_data)  # type: ignore
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    def test_api_documentation_available(self, client: TestClient) -> None:
        """Test that API documentation is available."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

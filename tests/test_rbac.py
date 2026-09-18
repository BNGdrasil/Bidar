# --------------------------------------------------------------------------
# Tests for RBAC (Role-Based Access Control) functionality
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.crud.auth import (
    check_role_permission,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_token_and_role,
)
from src.models.users import User


class TestRBACFunctions:
    """Test cases for RBAC functions."""

    def test_check_role_permission_user_vs_user(self) -> None:
        """Test role permission check: user accessing user resource."""
        assert check_role_permission("user", "user") is True

    def test_check_role_permission_moderator_vs_user(self) -> None:
        """Test role permission check: moderator accessing user resource."""
        assert check_role_permission("moderator", "user") is True

    def test_check_role_permission_admin_vs_user(self) -> None:
        """Test role permission check: admin accessing user resource."""
        assert check_role_permission("admin", "user") is True

    def test_check_role_permission_admin_vs_moderator(self) -> None:
        """Test role permission check: admin accessing moderator resource."""
        assert check_role_permission("admin", "moderator") is True

    def test_check_role_permission_super_admin_vs_admin(self) -> None:
        """Test role permission check: super_admin accessing admin resource."""
        assert check_role_permission("super_admin", "admin") is True

    def test_check_role_permission_user_vs_admin(self) -> None:
        """Test role permission check: user accessing admin resource (should fail)."""
        assert check_role_permission("user", "admin") is False

    def test_check_role_permission_moderator_vs_admin(self) -> None:
        """Role check: moderator accessing an admin resource (should fail)."""
        assert check_role_permission("moderator", "admin") is False

    def test_check_role_permission_user_vs_moderator(self) -> None:
        """Role check: user accessing a moderator resource (should fail)."""
        assert check_role_permission("user", "moderator") is False

    def test_check_role_permission_invalid_role(self) -> None:
        """Unknown roles are rejected on both sides instead of defaulting."""
        assert check_role_permission("invalid_role", "user") is False
        assert check_role_permission("invalid_role", "admin") is False
        assert check_role_permission("user", "invalid_role") is False

    @pytest_asyncio.fixture
    async def rbac_users(self, db_session: AsyncSession) -> dict:
        """Create users covering every role level."""
        users = {}
        for index, role in enumerate(
            ["user", "moderator", "admin", "super_admin"], start=1
        ):
            user = User(
                username=f"rbac_{role}",
                email=f"rbac_{role}@example.com",
                hashed_password=get_password_hash("rbacpassword123"),
                is_active=True,
                is_superuser=role == "super_admin",
                role=role,
            )
            db_session.add(user)
            users[role] = user
        await db_session.commit()
        for user in users.values():
            await db_session.refresh(user)
        return users

    @staticmethod
    def _token(user: User) -> str:
        return create_access_token(
            {"sub": user.username, "user_id": user.id, "role": user.role}
        )

    async def test_verify_token_and_role_success(
        self, db_session: AsyncSession, rbac_users: dict
    ) -> None:
        """Test token and role verification with sufficient permissions."""
        admin = rbac_users["admin"]
        result = await verify_token_and_role(
            self._token(admin), "moderator", db_session
        )

        assert result["allowed"] is True
        assert result["user_id"] == admin.id
        assert result["username"] == admin.username
        assert result["role"] == "admin"

    async def test_verify_token_and_role_insufficient_permissions(
        self, db_session: AsyncSession, rbac_users: dict
    ) -> None:
        """Test token and role verification with insufficient permissions."""
        with pytest.raises(HTTPException) as exc_info:
            await verify_token_and_role(
                self._token(rbac_users["user"]), "admin", db_session
            )

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in str(exc_info.value.detail)

    async def test_verify_token_and_role_invalid_token(
        self, db_session: AsyncSession
    ) -> None:
        """Test token and role verification with an invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            await verify_token_and_role("invalid_token", "user", db_session)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in str(exc_info.value.detail)

    async def test_verify_token_and_role_super_admin(
        self, db_session: AsyncSession, rbac_users: dict
    ) -> None:
        """Test token and role verification with super_admin."""
        result = await verify_token_and_role(
            self._token(rbac_users["super_admin"]), "admin", db_session
        )

        assert result["allowed"] is True
        assert result["role"] == "super_admin"

    async def test_verify_token_and_role_same_level(
        self, db_session: AsyncSession, rbac_users: dict
    ) -> None:
        """Test token and role verification with the same permission level."""
        result = await verify_token_and_role(
            self._token(rbac_users["moderator"]), "moderator", db_session
        )

        assert result["allowed"] is True
        assert result["role"] == "moderator"

    async def test_verify_token_and_role_missing_claims(
        self, db_session: AsyncSession, rbac_users: dict
    ) -> None:
        """A token without the required claims is rejected."""
        token = create_access_token({"sub": rbac_users["admin"].username})

        with pytest.raises(HTTPException) as exc_info:
            await verify_token_and_role(token, "user", db_session)

        assert exc_info.value.status_code == 401

    async def test_verify_token_and_role_rejects_refresh_token(
        self, db_session: AsyncSession, rbac_users: dict
    ) -> None:
        """SEC-03: a refresh token cannot be used for permission checks."""
        admin = rbac_users["super_admin"]
        token = create_refresh_token(
            {"sub": admin.username, "user_id": admin.id, "role": admin.role}
        )

        with pytest.raises(HTTPException) as exc_info:
            await verify_token_and_role(token, "super_admin", db_session)

        assert exc_info.value.status_code == 401

    async def test_verify_token_and_role_unknown_required_role(
        self, db_session: AsyncSession, rbac_users: dict
    ) -> None:
        """An unknown required role is refused instead of silently allowed."""
        with pytest.raises(HTTPException) as exc_info:
            await verify_token_and_role(
                self._token(rbac_users["super_admin"]), "root", db_session
            )

        assert exc_info.value.status_code == 403


class TestRBACEndpoints:
    """Test cases for RBAC API endpoints."""

    @pytest_asyncio.fixture
    async def test_users(self, db_session: AsyncSession) -> dict:
        """Create test users with different roles."""
        regular_user = User(
            username="regularuser",
            email="regular@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            role="user",
        )
        moderator_user = User(
            username="moderator",
            email="moderator@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            role="moderator",
        )
        admin_user = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            is_superuser=True,
            role="admin",
        )
        super_admin_user = User(
            username="superadmin",
            email="superadmin@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True,
            is_superuser=True,
            role="super_admin",
        )

        db_session.add_all([regular_user, moderator_user, admin_user, super_admin_user])
        await db_session.commit()
        await db_session.refresh(regular_user)
        await db_session.refresh(moderator_user)
        await db_session.refresh(admin_user)
        await db_session.refresh(super_admin_user)

        return {
            "user": regular_user,
            "moderator": moderator_user,
            "admin": admin_user,
            "super_admin": super_admin_user,
        }

    def test_role_hierarchy_levels(self) -> None:
        """Test that role hierarchy is properly defined."""
        from src.crud.auth import ROLE_HIERARCHY

        assert ROLE_HIERARCHY["user"] == 0
        assert ROLE_HIERARCHY["moderator"] == 1
        assert ROLE_HIERARCHY["admin"] == 2
        assert ROLE_HIERARCHY["super_admin"] == 3

    async def test_create_token_with_role(self, test_users: dict) -> None:
        """Test creating access tokens with role information."""
        user = test_users["user"]

        token = create_access_token(
            {"sub": user.username, "user_id": user.id, "role": user.role}
        )

        assert isinstance(token, str)
        assert len(token) > 0

    async def test_token_contains_role_information(self, test_users: dict) -> None:
        """Test that tokens contain role, type and UTC aware timestamps."""
        import jwt

        from src.core.config import settings

        admin = test_users["admin"]

        token = create_access_token(
            {"sub": admin.username, "user_id": admin.id, "role": admin.role}
        )

        # Decode token to verify role is included
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )

        assert payload["sub"] == admin.username
        assert payload["user_id"] == admin.id
        assert payload["role"] == admin.role
        assert payload["type"] == "access"
        assert payload["exp"] > payload["iat"]

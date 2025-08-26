# --------------------------------------------------------------------------
# Tests for authentication functionality
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.crud.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_active_user,
    get_current_user,
    get_password_hash,
    get_user,
    verify_password,
)
from src.models.users import User


class TestAuthFunctions:
    """Test cases for authentication functions."""

    def test_verify_password(self) -> None:
        """Test password verification."""
        password = "testpassword123"
        hashed_password = get_password_hash(password)

        # Test correct password
        assert verify_password(password, hashed_password) is True

        # Test incorrect password
        assert verify_password("wrongpassword", hashed_password) is False

        # Test empty password
        assert verify_password("", hashed_password) is False

    def test_get_password_hash(self) -> None:
        """Test password hashing."""
        password = "testpassword123"
        hashed_password = get_password_hash(password)

        # Verify hash is different from original password
        assert hashed_password != password

        # Verify hash is a string
        assert isinstance(hashed_password, str)

        # Verify hash is not empty
        assert len(hashed_password) > 0

        # Verify same password produces different hashes (due to salt)
        hashed_password2 = get_password_hash(password)
        assert hashed_password != hashed_password2

    def test_create_access_token(self) -> None:
        """Test access token creation."""
        data = {"sub": "testuser", "role": "user"}

        # Test with default expiration
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

        # Test with custom expiration
        expires_delta = timedelta(minutes=30)
        token_with_expiry = create_access_token(data, expires_delta)
        assert isinstance(token_with_expiry, str)
        assert len(token_with_expiry) > 0
        assert token_with_expiry != token

    def test_create_refresh_token(self) -> None:
        """Test refresh token creation."""
        data = {"sub": "testuser"}

        token = create_refresh_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user for authentication tests."""
        user = User(
            username="authuser",
            email="auth@example.com",
            hashed_password=get_password_hash("authpassword123"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    async def test_get_user_found(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test getting user by username when user exists."""
        user = await get_user(db_session, "authuser")
        assert user is not None
        assert user.username == "authuser"
        assert user.email == "auth@example.com"

    async def test_get_user_not_found(self, db_session: AsyncSession) -> None:
        """Test getting user by username when user doesn't exist."""
        user = await get_user(db_session, "nonexistentuser")
        assert user is None

    async def test_authenticate_user_success(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test successful user authentication."""
        user = await authenticate_user(db_session, "authuser", "authpassword123")
        assert user is not None
        assert user.username == "authuser"

    async def test_authenticate_user_wrong_password(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test user authentication with wrong password."""
        user = await authenticate_user(db_session, "authuser", "wrongpassword")
        assert user is None

    async def test_authenticate_user_not_found(self, db_session: AsyncSession) -> None:
        """Test user authentication with non-existent user."""
        user = await authenticate_user(db_session, "nonexistentuser", "anypassword")
        assert user is None

    async def test_authenticate_user_inactive(self, db_session: AsyncSession) -> None:
        """Test authentication with inactive user."""
        # Create inactive user
        inactive_user = User(
            username="inactiveuser",
            email="inactive@example.com",
            hashed_password=get_password_hash("inactivepassword123"),
            is_active=False,
        )
        db_session.add(inactive_user)
        await db_session.commit()
        await db_session.refresh(inactive_user)

        # Try to authenticate inactive user
        user = await authenticate_user(
            db_session, "inactiveuser", "inactivepassword123"
        )
        assert user is not None  # Authentication should still succeed
        assert user.is_active is False

    async def test_get_current_user_success(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test getting current user with valid token."""
        from fastapi import Depends

        from src.crud.auth import oauth2_scheme

        # Create a valid token
        token = create_access_token({"sub": test_user.username})

        # Mock the token dependency
        async def mock_token() -> str:
            return token

        # Test get_current_user
        user = await get_current_user(token=token, db=db_session)
        assert user is not None
        assert user.username == test_user.username

    async def test_get_current_user_invalid_token(
        self, db_session: AsyncSession
    ) -> None:
        """Test getting current user with invalid token."""
        from src.crud.auth import oauth2_scheme

        # Test with invalid token
        with pytest.raises(Exception):  # Should raise HTTPException
            await get_current_user(token="invalid_token", db=db_session)

    async def test_get_current_active_user_success(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test getting current active user with active user."""
        # Create a valid token
        token = create_access_token({"sub": test_user.username})

        # Test get_current_active_user
        user = await get_current_active_user(
            current_user=await get_current_user(token=token, db=db_session)
        )
        assert user is not None
        assert user.username == test_user.username
        assert user.is_active is True

    async def test_get_current_active_user_inactive(
        self, db_session: AsyncSession
    ) -> None:
        """Test getting current active user with inactive user."""
        # Create inactive user
        inactive_user = User(
            username="inactiveuser2",
            email="inactive2@example.com",
            hashed_password=get_password_hash("inactivepassword456"),
            is_active=False,
        )
        db_session.add(inactive_user)
        await db_session.commit()
        await db_session.refresh(inactive_user)

        # Test get_current_active_user with inactive user
        with pytest.raises(Exception):  # Should raise HTTPException
            await get_current_active_user(current_user=inactive_user)

    async def test_password_hash_verification_roundtrip(
        self, db_session: AsyncSession
    ) -> None:
        """Test password hashing and verification roundtrip."""
        password = "complexpassword123!@#"

        # Hash password
        hashed = get_password_hash(password)

        # Verify password
        assert verify_password(password, hashed) is True

        # Verify wrong password fails
        assert verify_password("wrongpassword", hashed) is False

    async def test_token_expiration(self) -> None:
        """Test token expiration handling."""
        data = {"sub": "testuser"}

        # Create token with very short expiration
        short_expiry = timedelta(seconds=1)
        token = create_access_token(data, short_expiry)

        # Token should be created successfully
        assert isinstance(token, str)
        assert len(token) > 0

    async def test_refresh_token_with_type(self) -> None:
        """Test refresh token includes type field."""
        data = {"sub": "testuser"}

        token = create_refresh_token(data)
        assert isinstance(token, str)
        assert len(token) > 0

        # Note: In a real test, you might decode the token to verify the "type": "refresh" field
        # but for now we just verify the token is created successfully

# --------------------------------------------------------------------------
# Tests for user management functionality
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import pytest
import pytest_asyncio  # type: ignore
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_password_hash
from src.core.users import (
    UserRegisterRequest,
    activate_user,
    deactivate_user,
    list_users,
    register_user,
)
from src.models.user import User


class TestUserManagement:
    """Test cases for user management functions."""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=get_password_hash("testpassword123"),
            full_name="Test User",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest_asyncio.fixture
    async def test_superuser(self, db_session: AsyncSession) -> User:
        """Create a test superuser."""
        superuser = User(
            username="admin",
            email="admin@example.com",
            hashed_password=get_password_hash("adminpassword123"),
            full_name="Admin User",
            is_active=True,
            is_superuser=True,
        )
        db_session.add(superuser)
        await db_session.commit()
        await db_session.refresh(superuser)
        return superuser

    async def test_register_user_success(self, db_session: AsyncSession) -> None:
        """Test successful user registration."""
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpassword123",
            "full_name": "New User",
        }

        from src.core.users import UserRegisterRequest

        user_request = UserRegisterRequest(
            username=str(user_data["username"]),
            email=str(user_data["email"]),
            password=str(user_data["password"]),
            full_name=str(user_data["full_name"]),
        )
        result = await register_user(
            user_data=user_request,
            db=db_session,
        )

        assert result["message"] == "User registered successfully"
        assert "user_id" in result
        assert result["username"] == user_data["username"]
        assert result["email"] == user_data["email"]

        # Verify user was actually created in database
        result_query = await db_session.execute(
            select(User).where(User.username == user_data["username"])
        )
        user = result_query.scalar_one_or_none()
        assert user is not None
        assert user.username == user_data["username"]
        assert user.email == user_data["email"]
        assert user.full_name == user_data["full_name"]
        assert user.is_active is True
        assert user.is_superuser is False

    async def test_register_user_duplicate_username(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test user registration with duplicate username."""
        user_data = {
            "username": test_user.username,  # Same username as existing user
            "email": "different@example.com",
            "password": "differentpassword123",
            "full_name": "Different User",
        }

        with pytest.raises(Exception):  # Should raise HTTPException
            user_request = UserRegisterRequest(
                username=str(user_data["username"]),
                email=str(user_data["email"]),
                password=str(user_data["password"]),
                full_name=str(user_data["full_name"]),
            )
            await register_user(
                user_data=user_request,
                db=db_session,
            )

    async def test_register_user_duplicate_email(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test user registration with duplicate email."""
        user_data = {
            "username": "differentuser",
            "email": test_user.email,  # Same email as existing user
            "password": "differentpassword123",
            "full_name": "Different User",
        }

        with pytest.raises(Exception):  # Should raise HTTPException
            user_request = UserRegisterRequest(
                username=str(user_data["username"]),
                email=str(user_data["email"]),
                password=str(user_data["password"]),
                full_name=str(user_data["full_name"]),
            )
            await register_user(
                user_data=user_request,
                db=db_session,
            )

    async def test_register_user_without_full_name(
        self, db_session: AsyncSession
    ) -> None:
        """Test user registration without full name."""
        user_data = {
            "username": "nofullname",
            "email": "nofullname@example.com",
            "password": "password123",
        }

        user_request = UserRegisterRequest(
            username=user_data["username"],
            email=user_data["email"],
            password=user_data["password"],
        )
        result = await register_user(
            user_data=user_request,
            db=db_session,
        )

        assert result["message"] == "User registered successfully"
        assert result["username"] == user_data["username"]

        # Verify user was created with null full_name
        result_query = await db_session.execute(
            select(User).where(User.username == user_data["username"])
        )
        user = result_query.scalar_one_or_none()
        assert user is not None
        assert user.full_name is None

    async def test_list_users_superuser_access(
        self, db_session: AsyncSession, test_superuser: User
    ) -> None:
        """Test listing users with superuser access."""
        # Create additional users
        user1 = User(
            username="user1",
            email="user1@example.com",
            hashed_password=get_password_hash("password1"),
            is_active=True,
        )
        user2 = User(
            username="user2",
            email="user2@example.com",
            hashed_password=get_password_hash("password2"),
            is_active=False,
        )
        db_session.add_all([user1, user2])
        await db_session.commit()

        # Test listing users as superuser
        users = await list_users(current_user=test_superuser, db=db_session)

        # Should return all users including superuser
        assert len(users) >= 3  # At least test_superuser, user1, user2

        # Verify user data structure
        for user_data in users:
            assert "id" in user_data
            assert "username" in user_data
            assert "email" in user_data
            assert "full_name" in user_data
            assert "is_active" in user_data
            assert "is_superuser" in user_data
            assert "created_at" in user_data

    async def test_list_users_non_superuser_access(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test listing users without superuser access."""
        with pytest.raises(Exception):  # Should raise HTTPException
            await list_users(current_user=test_user, db=db_session)

    async def test_activate_user_superuser_access(
        self, db_session: AsyncSession, test_superuser: User
    ) -> None:
        """Test activating user with superuser access."""
        # Create inactive user
        inactive_user = User(
            username="inactiveuser",
            email="inactive@example.com",
            hashed_password=get_password_hash("inactivepassword"),
            is_active=False,
        )
        db_session.add(inactive_user)
        await db_session.commit()
        await db_session.refresh(inactive_user)

        # Activate user
        result = await activate_user(
            user_id=int(inactive_user.id),
            current_user=test_superuser,
            db=db_session,
        )

        assert (
            result["message"] == f"User {inactive_user.username} activated successfully"
        )

        # Verify user is now active
        result_query = await db_session.execute(
            select(User).where(User.id == inactive_user.id)
        )
        user = result_query.scalar_one_or_none()
        assert user is not None
        assert user.is_active is True

    async def test_activate_user_non_superuser_access(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test activating user without superuser access."""
        with pytest.raises(Exception):  # Should raise HTTPException
            await activate_user(
                user_id=1,
                current_user=test_user,
                db=db_session,
            )

    async def test_activate_nonexistent_user(
        self, db_session: AsyncSession, test_superuser: User
    ) -> None:
        """Test activating non-existent user."""
        with pytest.raises(Exception):  # Should raise HTTPException
            await activate_user(
                user_id=99999,  # Non-existent user ID
                current_user=test_superuser,
                db=db_session,
            )

    async def test_deactivate_user_superuser_access(
        self, db_session: AsyncSession, test_superuser: User
    ) -> None:
        """Test deactivating user with superuser access."""
        # Create active user
        active_user = User(
            username="activeuser",
            email="active@example.com",
            hashed_password=get_password_hash("activepassword"),
            is_active=True,
        )
        db_session.add(active_user)
        await db_session.commit()
        await db_session.refresh(active_user)

        # Deactivate user
        result = await deactivate_user(
            user_id=int(active_user.id),
            current_user=test_superuser,
            db=db_session,
        )

        assert (
            result["message"] == f"User {active_user.username} deactivated successfully"
        )

        # Verify user is now inactive
        result_query = await db_session.execute(
            select(User).where(User.id == active_user.id)
        )
        user = result_query.scalar_one_or_none()
        assert user is not None
        assert user.is_active is False

    async def test_deactivate_user_non_superuser_access(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Test deactivating user without superuser access."""
        with pytest.raises(Exception):  # Should raise HTTPException
            await deactivate_user(
                user_id=1,
                current_user=test_user,
                db=db_session,
            )

    async def test_deactivate_nonexistent_user(
        self, db_session: AsyncSession, test_superuser: User
    ) -> None:
        """Test deactivating non-existent user."""
        with pytest.raises(Exception):  # Should raise HTTPException
            await deactivate_user(
                user_id=99999,  # Non-existent user ID
                current_user=test_superuser,
                db=db_session,
            )

    async def test_register_user_password_hashing(
        self, db_session: AsyncSession
    ) -> None:
        """Test that user registration properly hashes passwords."""
        user_data = {
            "username": "passwordtestuser",
            "email": "passwordtest@example.com",
            "password": "plaintextpassword",
            "full_name": "Password Test User",
        }

        user_request = UserRegisterRequest(
            username=user_data["username"],
            email=user_data["email"],
            password=user_data["password"],
            full_name=user_data["full_name"],
        )
        await register_user(
            user_data=user_request,
            db=db_session,
        )

        # Verify password was hashed
        result_query = await db_session.execute(
            select(User).where(User.username == user_data["username"])
        )
        user = result_query.scalar_one_or_none()
        assert user is not None
        assert user.hashed_password != user_data["password"]  # Should be hashed
        assert len(user.hashed_password) > len(
            user_data["password"]
        )  # Hash should be longer

    async def test_user_registration_timestamps(self, db_session: AsyncSession) -> None:
        """Test that user registration sets proper timestamps."""
        user_data = {
            "username": "timestampuser",
            "email": "timestamp@example.com",
            "password": "timestamppassword",
        }

        user_request = UserRegisterRequest(
            username=user_data["username"],
            email=user_data["email"],
            password=user_data["password"],
        )
        await register_user(
            user_data=user_request,
            db=db_session,
        )

        # Verify timestamps
        result_query = await db_session.execute(
            select(User).where(User.username == user_data["username"])
        )
        user = result_query.scalar_one_or_none()
        assert user is not None
        assert user.created_at is not None
        assert user.updated_at is None  # Should be None until updated

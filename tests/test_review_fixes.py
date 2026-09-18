# --------------------------------------------------------------------------
# Regression tests for the cross review findings
#
# One class per finding so a failure names the contract that regressed.
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import os
from typing import Any, Dict
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.passwords import BCRYPT_MAX_PASSWORD_BYTES, PasswordTooLongError
from src.core.ratelimit import MAX_TRACKED_KEYS, SlidingWindowLimiter
from src.crud.auth import create_access_token, get_password_hash, verify_password
from src.crud.users import LastSuperAdminError, deactivate_user
from src.models.users import User, UserCreate

STRONG_TEST_KEY = "Tn6qzE2sWvJ4hLpR9xYb3MdKgC7uAfZq"

# Exactly 72 bytes in UTF-8: 24 Hangul syllables at three bytes each.
SEVENTY_TWO_BYTES = "가" * 24


def build_settings(**env: str) -> Settings:
    """Build Settings from an explicit environment, ignoring any local .env."""
    with patch.dict(os.environ, env, clear=True):
        return Settings(_env_file=None)  # type: ignore[call-arg]


async def _add_user(db: AsyncSession, **kwargs: Any) -> User:
    user = User(**kwargs)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth(user: User) -> Dict[str, str]:
    token = create_access_token(
        {"sub": user.username, "user_id": user.id, "role": user.role}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def cast(db_session: AsyncSession) -> Dict[str, User]:
    """One account per role, plus a second admin and a second super admin."""
    created: Dict[str, User] = {}
    definitions = [
        ("super_admin", "boss", "super_admin", True),
        ("super_admin2", "boss2", "super_admin", True),
        ("admin", "manager", "admin", False),
        ("admin2", "manager2", "admin", False),
        ("moderator", "mod", "moderator", False),
        ("user", "plain", "user", False),
    ]
    for key, username, role, is_superuser in definitions:
        created[key] = await _add_user(
            db_session,
            username=username,
            email=f"{username}@example.com",
            hashed_password=get_password_hash("reviewfixpassword123"),
            is_active=True,
            is_superuser=is_superuser,
            role=role,
        )
    return created


class TestActivationTargetRole:
    """Finding 1: activate/deactivate must consider the target's role."""

    def test_admin_cannot_deactivate_super_admin(
        self, client: TestClient, cast: Dict[str, User]
    ) -> None:
        """An admin deactivating a super admin is refused."""
        response = client.put(
            f"/users/users/{cast['super_admin'].id}/deactivate",
            headers=_auth(cast["admin"]),
        )
        assert response.status_code == 403
        assert response.json() == {
            "detail": "Only a super admin can manage an admin account"
        }

    def test_admin_cannot_deactivate_peer_admin(
        self, client: TestClient, cast: Dict[str, User]
    ) -> None:
        """An admin cannot remove another admin either."""
        response = client.put(
            f"/users/users/{cast['admin2'].id}/deactivate",
            headers=_auth(cast["admin"]),
        )
        assert response.status_code == 403

    def test_admin_cannot_activate_super_admin(
        self, client: TestClient, cast: Dict[str, User]
    ) -> None:
        """The same rule applies to activation."""
        response = client.put(
            f"/users/users/{cast['super_admin2'].id}/activate",
            headers=_auth(cast["admin"]),
        )
        assert response.status_code == 403

    def test_admin_may_manage_moderator_and_user(
        self, client: TestClient, cast: Dict[str, User]
    ) -> None:
        """Accounts below admin level stay manageable by an admin."""
        for key in ("moderator", "user"):
            response = client.put(
                f"/users/users/{cast[key].id}/deactivate",
                headers=_auth(cast["admin"]),
            )
            assert response.status_code == 200, key

    def test_super_admin_may_manage_admin(
        self, client: TestClient, cast: Dict[str, User]
    ) -> None:
        """A super admin is exempt from the restriction."""
        response = client.put(
            f"/users/users/{cast['admin'].id}/deactivate",
            headers=_auth(cast["super_admin"]),
        )
        assert response.status_code == 200

    def test_super_admin_may_deactivate_peer_super_admin(
        self, client: TestClient, cast: Dict[str, User]
    ) -> None:
        """With a spare super admin the last-super-admin guard allows it."""
        response = client.put(
            f"/users/users/{cast['super_admin2'].id}/deactivate",
            headers=_auth(cast["super_admin"]),
        )
        assert response.status_code == 200

    def test_self_deactivation_is_400(
        self, client: TestClient, cast: Dict[str, User]
    ) -> None:
        """An operator cannot lock themselves out, super admin or not."""
        response = client.put(
            f"/users/users/{cast['admin'].id}/deactivate",
            headers=_auth(cast["admin"]),
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "You cannot deactivate your own account"}

    def test_self_deactivation_is_400_for_super_admin(
        self, client: TestClient, cast: Dict[str, User]
    ) -> None:
        """The self check is independent of the last-super-admin guard."""
        response = client.put(
            f"/users/users/{cast['super_admin'].id}/deactivate",
            headers=_auth(cast["super_admin"]),
        )
        assert response.status_code == 400

    def test_unknown_target_is_404(
        self, client: TestClient, cast: Dict[str, User]
    ) -> None:
        """A missing target is still a 404, not a 403."""
        response = client.put(
            "/users/users/999999/deactivate", headers=_auth(cast["admin"])
        )
        assert response.status_code == 404


class TestPasswordByteLimit:
    """Finding 2: bcrypt truncation must not merge distinct passwords."""

    def test_distinct_long_passwords_do_not_authenticate(self) -> None:
        """Two passwords sharing a 72 byte prefix stay distinct."""
        original = SEVENTY_TWO_BYTES + "original"
        different = SEVENTY_TWO_BYTES + "different"

        # Neither can be hashed at all now, which is the point: the old code
        # truncated both to the same 72 bytes and made them interchangeable.
        with pytest.raises(PasswordTooLongError):
            get_password_hash(original)

        boundary_hash = get_password_hash(SEVENTY_TWO_BYTES)
        assert verify_password(original, boundary_hash) is False
        assert verify_password(different, boundary_hash) is False

    def test_verify_rejects_overlong_candidate_without_raising(self) -> None:
        """An overlong candidate is False, never an exception."""
        stored = get_password_hash("short-enough-password")
        assert verify_password("x" * 200, stored) is False

    def test_boundary_password_still_works(self) -> None:
        """Exactly 72 bytes is accepted and round-trips."""
        assert len(SEVENTY_TWO_BYTES.encode("utf-8")) == BCRYPT_MAX_PASSWORD_BYTES
        stored = get_password_hash(SEVENTY_TWO_BYTES)
        assert verify_password(SEVENTY_TWO_BYTES, stored) is True

    def test_user_create_rejects_overlong_password(self) -> None:
        """The admin creation schema refuses it with a validation error."""
        with pytest.raises(ValidationError):
            UserCreate(
                username="toolong",
                email="toolong@example.com",
                password=SEVENTY_TWO_BYTES + "original",
            )

    def test_user_create_accepts_boundary_password(self) -> None:
        """A password of exactly 72 bytes validates."""
        model = UserCreate(
            username="boundary",
            email="boundary@example.com",
            password=SEVENTY_TWO_BYTES,
        )
        assert model.password == SEVENTY_TWO_BYTES

    def test_create_endpoint_returns_422(
        self, client: TestClient, cast: Dict[str, User]
    ) -> None:
        """POST /users answers 422 rather than a 500 from bcrypt."""
        response = client.post(
            "/users",
            json={
                "username": "toolong",
                "email": "toolong@example.com",
                "password": SEVENTY_TWO_BYTES + "original",
            },
            headers=_auth(cast["super_admin"]),
        )
        assert response.status_code == 422

    def test_cli_rejects_overlong_password(self) -> None:
        """The CLI refuses it before touching the database."""
        from src.cli import _validate_password

        with pytest.raises(SystemExit):
            _validate_password(SEVENTY_TWO_BYTES + "original")


class TestLastSuperAdminLocking:
    """Finding 3: the guard locks the rows it counts."""

    async def test_guard_uses_row_locking(
        self, db_session: AsyncSession, cast: Dict[str, User]
    ) -> None:
        """The emitted statement carries FOR UPDATE.

        SQLite ignores row locking, so this asserts on the compiled SQL to
        prove the lock is requested on a dialect that honours it.
        """
        from sqlalchemy.dialects import postgresql
        from sqlmodel import select as sqlmodel_select

        statement = (
            sqlmodel_select(User)
            .where(User.role == "super_admin")
            .where(User.is_active == True)  # noqa: E712
            .order_by(User.id)  # type: ignore[arg-type]
            .with_for_update()
        )
        compiled = str(statement.compile(dialect=postgresql.dialect()))
        assert "FOR UPDATE" in compiled

        import inspect

        from src.crud import users as users_crud

        source = inspect.getsource(users_crud._guard_last_super_admin)
        assert "with_for_update()" in source
        assert "order_by" in source

    async def test_guard_still_allows_demotion_with_a_spare(
        self, db_session: AsyncSession, cast: Dict[str, User]
    ) -> None:
        """Locking does not change the outcome when a spare exists."""
        result = await deactivate_user(db_session, int(cast["super_admin"].id or 0))
        assert result is not None
        assert result.is_active is False

    async def test_guard_refuses_the_last_one(
        self, db_session: AsyncSession, cast: Dict[str, User]
    ) -> None:
        """Once the spare is gone the guard fires."""
        await deactivate_user(db_session, int(cast["super_admin2"].id or 0))
        with pytest.raises(LastSuperAdminError):
            await deactivate_user(db_session, int(cast["super_admin"].id or 0))


class TestLimiterCapacity:
    """Finding 6: MAX_TRACKED_KEYS is a real ceiling."""

    def test_key_map_is_bounded(self) -> None:
        """Flooding distinct keys does not grow the map past the ceiling."""
        limiter = SlidingWindowLimiter()
        for index in range(MAX_TRACKED_KEYS + 2):
            limiter.hit(f"key-{index}", 10)
        assert len(limiter._events) <= MAX_TRACKED_KEYS

    def test_eviction_is_least_recently_used(self) -> None:
        """The oldest untouched key is the one dropped."""
        limiter = SlidingWindowLimiter(max_tracked_keys=3)
        for key in ("a", "b", "c"):
            limiter.hit(key, 10)
        limiter.hit("a", 10)  # refresh "a" so "b" becomes the oldest
        limiter.hit("d", 10)
        assert "b" not in limiter._events
        assert set(limiter._events) == {"a", "c", "d"}

    def test_limit_still_enforced_after_eviction(self) -> None:
        """Eviction does not break counting for the surviving keys."""
        limiter = SlidingWindowLimiter(max_tracked_keys=2)
        assert [limiter.hit("x", 2) for _ in range(3)] == [True, True, False]


class TestProductionHostValidation:
    """Finding 7: host and origin lists are required in production."""

    def _prod(self, **extra: str) -> Dict[str, str]:
        env = {
            "ENVIRONMENT": "production",
            "JWT_SECRET_KEY": STRONG_TEST_KEY,
            "DATABASE_URL": "postgresql://u:p@db:5432/bngdrasil",
        }
        env.update(extra)
        return env

    @pytest.mark.parametrize("name", ["ALLOWED_HOSTS", "ALLOWED_ORIGINS"])
    def test_missing_list_fails_in_production(self, name: str) -> None:
        """An unset list stops the server in production."""
        env = self._prod()
        other = "ALLOWED_ORIGINS" if name == "ALLOWED_HOSTS" else "ALLOWED_HOSTS"
        env[other] = "example.com"
        with pytest.raises(ValidationError) as exc_info:
            build_settings(**env)
        assert name in str(exc_info.value)

    @pytest.mark.parametrize("name", ["ALLOWED_HOSTS", "ALLOWED_ORIGINS"])
    def test_empty_list_fails_in_production(self, name: str) -> None:
        """An explicitly empty value is refused too."""
        env = self._prod(ALLOWED_HOSTS="example.com", ALLOWED_ORIGINS="example.com")
        env[name] = " , "
        with pytest.raises(ValidationError) as exc_info:
            build_settings(**env)
        assert name in str(exc_info.value)

    @pytest.mark.parametrize("name", ["ALLOWED_HOSTS", "ALLOWED_ORIGINS"])
    def test_wildcard_fails_in_production(self, name: str) -> None:
        """A wildcard is refused outright, matching Bifrost."""
        env = self._prod(
            ALLOWED_HOSTS="api.bnbong.com",
            ALLOWED_ORIGINS="https://admin.bnbong.com",
        )
        env[name] = "*"
        with pytest.raises(ValidationError) as exc_info:
            build_settings(**env)
        message = str(exc_info.value)
        assert name in message
        assert "must not contain" in message

    def test_wildcard_among_real_values_also_fails(self) -> None:
        """A wildcard mixed into a real list is still refused."""
        with pytest.raises(ValidationError):
            build_settings(
                **self._prod(
                    ALLOWED_HOSTS="api.bnbong.com,*",
                    ALLOWED_ORIGINS="https://admin.bnbong.com",
                )
            )

    def test_explicit_lists_are_accepted(self) -> None:
        """Named hosts and origins start normally."""
        settings = build_settings(
            **self._prod(
                ALLOWED_HOSTS="api.bnbong.com,auth-server,localhost",
                ALLOWED_ORIGINS="https://admin.bnbong.com,https://bnbong.com",
            )
        )
        assert settings.ALLOWED_HOSTS == [
            "api.bnbong.com",
            "auth-server",
            "localhost",
        ]
        assert settings.ALLOWED_ORIGINS == [
            "https://admin.bnbong.com",
            "https://bnbong.com",
        ]

    def test_development_still_defaults_to_wildcard(self) -> None:
        """Development is unchanged: the wildcard rule is production only."""
        settings = build_settings()
        assert settings.ALLOWED_HOSTS == ["*"]
        assert settings.ALLOWED_ORIGINS == ["*"]

    def test_test_environment_allows_wildcard(self) -> None:
        """The test environment keeps working with an explicit wildcard."""
        settings = build_settings(ENVIRONMENT="test", ALLOWED_HOSTS="*")
        assert settings.ALLOWED_HOSTS == ["*"]


class TestSharedPasswordPolicy:
    """The CLI and the admin schema enforce the same minimum length."""

    def test_minimum_length_is_shared(self) -> None:
        """Both callers read the same constant."""
        from src.cli import MIN_PASSWORD_LENGTH as cli_minimum
        from src.core.passwords import MIN_PASSWORD_LENGTH as core_minimum

        assert cli_minimum is core_minimum
        assert core_minimum == 12

    def test_user_create_rejects_a_short_password(self) -> None:
        """Eleven characters is refused by the schema."""
        with pytest.raises(ValidationError):
            UserCreate(
                username="shorty",
                email="shorty@example.com",
                password="a" * 11,
            )

    def test_user_create_accepts_the_minimum(self) -> None:
        """Twelve characters is accepted."""
        model = UserCreate(
            username="justlong",
            email="justlong@example.com",
            password="a" * 12,
        )
        assert model.password == "a" * 12

    def test_cli_rejects_a_short_password(self) -> None:
        """The CLI refuses the same input."""
        from src.cli import _validate_password

        with pytest.raises(SystemExit):
            _validate_password("a" * 11)
        _validate_password("a" * 12)

    def test_dev_database_url_uses_the_real_database_name(self) -> None:
        """The development fallback points at bngdrasil, not bnbong."""
        from src.core.config import DEV_DATABASE_URL

        assert DEV_DATABASE_URL.rsplit("/", 1)[-1] == "bngdrasil"
        assert build_settings().DATABASE_URL == DEV_DATABASE_URL

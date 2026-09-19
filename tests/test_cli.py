# --------------------------------------------------------------------------
# Tests for the administrative CLI
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import contextlib
import os
from typing import Iterator
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.cli import (
    NEW_PASSWORD_ENV_VAR,
    PASSWORD_ENV_VAR,
    _read_password,
    _reset_password,
    _validate_password,
    build_parser,
)
from src.core.passwords import BCRYPT_MAX_PASSWORD_BYTES
from tests.conftest import TestingSessionLocal


class TestCreateAdminCli:
    """The CLI must never take a password from the command line."""

    def test_parser_has_no_password_argument(self) -> None:
        """No --password option exists, so nothing lands in the shell history."""
        parser = build_parser()
        args = parser.parse_args(
            ["create-admin", "--username", "root", "--email", "root@example.com"]
        )
        assert not hasattr(args, "password")
        assert args.role == "super_admin"

    def test_parser_rejects_unknown_role(self) -> None:
        """An unknown role is refused before any database work."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "create-admin",
                    "--username",
                    "root",
                    "--email",
                    "root@example.com",
                    "--role",
                    "root",
                ]
            )

    def test_password_read_from_environment(self) -> None:
        """The password comes from the environment variable when set."""
        with patch.dict(os.environ, {PASSWORD_ENV_VAR: "env-provided-password"}):
            assert _read_password(non_interactive=True) == "env-provided-password"

    def test_non_interactive_without_environment_fails(self) -> None:
        """Without the variable and without a terminal the CLI stops."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit):
                _read_password(non_interactive=True)

    def test_short_password_rejected(self) -> None:
        """A short password is refused."""
        with pytest.raises(SystemExit):
            _validate_password("short")

    def test_long_password_accepted(self) -> None:
        """A sufficiently long password passes validation."""
        _validate_password("a-long-enough-password")


class _StubEngine:
    """Stand-in for the application engine; the test engine outlives the CLI."""

    async def dispose(self) -> None:
        """Do nothing: the session scoped test engine must stay open."""


@contextlib.contextmanager
def _cli_uses_test_database() -> Iterator[None]:
    """Point the CLI database imports at the in-memory test database."""
    import src.core.database as database

    async def _noop_init_db() -> None:
        pass

    with (
        patch.object(database, "init_db", _noop_init_db),
        patch.object(database, "AsyncSessionLocal", TestingSessionLocal),
        patch.object(database, "engine", _StubEngine()),
    ):
        yield


async def _create_account(
    db_session: AsyncSession, username: str, is_active: bool = True
) -> None:
    """Insert one account to reset the password of."""
    from src.crud.users import create_user
    from src.models.users import UserCreate

    await create_user(
        db_session,
        UserCreate(
            username=username,
            email=f"{username}@example.com",
            password="initial-password",
            role="super_admin",
            is_active=is_active,
        ),
    )


class TestResetPasswordCli:
    """reset-password takes the new password from the environment or a prompt."""

    def test_parser_has_no_password_argument(self) -> None:
        """No --password option exists, so nothing lands in the shell history."""
        parser = build_parser()
        args = parser.parse_args(["reset-password", "--username", "bnbong"])
        assert args.command == "reset-password"
        assert args.username == "bnbong"
        assert not hasattr(args, "password")

    def test_parser_rejects_a_positional_password(self) -> None:
        """A password passed as an argument is refused instead of accepted."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(
                ["reset-password", "--username", "bnbong", "--password", "secret"]
            )

    def test_password_read_from_its_own_environment_variable(self) -> None:
        """reset-password reads BIDAR_NEW_PASSWORD, not the create-admin one."""
        with patch.dict(os.environ, {NEW_PASSWORD_ENV_VAR: "new-password-value"}):
            assert (
                _read_password(non_interactive=True, env_var=NEW_PASSWORD_ENV_VAR)
                == "new-password-value"
            )

    def test_create_admin_variable_is_not_reused(self) -> None:
        """The create-admin password does not silently reset an account."""
        with patch.dict(os.environ, {PASSWORD_ENV_VAR: "admin-password"}, clear=True):
            with pytest.raises(SystemExit):
                _read_password(non_interactive=True, env_var=NEW_PASSWORD_ENV_VAR)

    def test_short_password_rejected(self) -> None:
        """The shared minimum length applies to a reset as well."""
        with pytest.raises(SystemExit):
            _validate_password("short")

    def test_password_over_seventy_two_bytes_rejected(self) -> None:
        """A password bcrypt cannot hash, over 72 bytes, is refused."""
        too_long = "가" * 25  # 75 bytes in UTF-8
        assert len(too_long.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES
        with pytest.raises(SystemExit):
            _validate_password(too_long)

    async def test_reset_updates_the_stored_hash(
        self, db_session: AsyncSession, capsys: pytest.CaptureFixture
    ) -> None:
        """A successful reset replaces the hash and reports the account."""
        from src.crud.auth import verify_password
        from src.crud.users import get_user_by_username

        await _create_account(db_session, "bnbong")

        with _cli_uses_test_database():
            exit_code = await _reset_password("bnbong", "brand-new-password")

        assert exit_code == 0
        assert "Password updated for bnbong" in capsys.readouterr().out

        db_session.expire_all()
        user = await get_user_by_username(db_session, "bnbong")
        assert user is not None
        assert verify_password("brand-new-password", user.hashed_password)
        assert not verify_password("initial-password", user.hashed_password)

    async def test_unknown_user_exits_with_one(
        self, db_session: AsyncSession, capsys: pytest.CaptureFixture
    ) -> None:
        """An unknown account is reported on stderr and exits non-zero."""
        with _cli_uses_test_database():
            exit_code = await _reset_password("nobody", "brand-new-password")

        assert exit_code == 1
        assert "does not exist" in capsys.readouterr().err

    async def test_inactive_account_is_warned_about_but_reset(
        self, db_session: AsyncSession, capsys: pytest.CaptureFixture
    ) -> None:
        """A deactivated account still gets the new password, with a warning."""
        from src.crud.auth import verify_password
        from src.crud.users import get_user_by_username

        await _create_account(db_session, "dormant", is_active=False)

        with _cli_uses_test_database():
            exit_code = await _reset_password("dormant", "brand-new-password")

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "inactive" in captured.err
        assert "Password updated for dormant" in captured.out

        db_session.expire_all()
        user = await get_user_by_username(db_session, "dormant")
        assert user is not None
        assert verify_password("brand-new-password", user.hashed_password)

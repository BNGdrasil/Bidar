# --------------------------------------------------------------------------
# Tests for the administrative CLI
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import os
from unittest.mock import patch

import pytest

from src.cli import PASSWORD_ENV_VAR, _read_password, _validate_password, build_parser


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

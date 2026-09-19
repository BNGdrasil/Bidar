# --------------------------------------------------------------------------
# Administrative command line interface
#
# Usage:
#   python -m src.cli create-admin --username admin --email admin@example.com
#   python -m src.cli reset-password --username admin
#
# The password is never accepted as a command line argument. It is read from
# an environment variable (BIDAR_ADMIN_PASSWORD for create-admin,
# BIDAR_NEW_PASSWORD for reset-password) or prompted for interactively, so it
# does not end up in the shell history or in the process table.
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import argparse
import asyncio
import getpass
import os
import sys
from typing import Optional

from src.core.passwords import (
    BCRYPT_MAX_PASSWORD_BYTES,
    MIN_PASSWORD_LENGTH,
    is_password_length_supported,
    password_byte_length,
)
from src.core.roles import SUPER_ADMIN_ROLE, VALID_ROLES
from src.models.users import UserCreate

# bandit B105 (false positives): these are the names of the variables, never
# a password value.
PASSWORD_ENV_VAR = "BIDAR_ADMIN_PASSWORD"  # nosec B105
NEW_PASSWORD_ENV_VAR = "BIDAR_NEW_PASSWORD"  # nosec B105


def _read_password(non_interactive: bool, env_var: str = PASSWORD_ENV_VAR) -> str:
    """Read the new account password from the environment or a prompt."""
    password = os.environ.get(env_var)
    if password:
        return password

    if non_interactive or not sys.stdin.isatty():
        raise SystemExit(
            f"{env_var} is not set and no interactive terminal is "
            "available. Export the variable and retry."
        )

    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Repeat password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    return password


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    if not is_password_length_supported(password):
        # bcrypt cannot hash more than 72 bytes and truncating would make two
        # different passwords equivalent, so this is refused rather than cut.
        raise SystemExit(
            "Password must be at most "
            f"{BCRYPT_MAX_PASSWORD_BYTES} bytes when encoded as UTF-8 "
            f"(this one is {password_byte_length(password)} bytes). "
            "Non-ASCII characters take more than one byte each."
        )


async def _create_admin(
    username: str, email: str, full_name: Optional[str], role: str, password: str
) -> int:
    from src.core.database import AsyncSessionLocal, engine, init_db
    from src.crud.users import create_user, get_user_by_email, get_user_by_username

    await init_db()
    try:
        async with AsyncSessionLocal() as db:
            if await get_user_by_username(db, username):
                print(f"User '{username}' already exists.", file=sys.stderr)
                return 1
            if await get_user_by_email(db, email):
                print(f"Email '{email}' already exists.", file=sys.stderr)
                return 1

            user = await create_user(
                db,
                UserCreate(
                    username=username,
                    email=email,
                    full_name=full_name,
                    password=password,
                    role=role,
                    is_active=True,
                ),
            )
            print(
                f"Created user id={user.id} username={user.username} role={user.role}"
            )
            return 0
    finally:
        await engine.dispose()


async def _reset_password(username: str, password: str) -> int:
    from src.core.database import AsyncSessionLocal, engine, init_db
    from src.crud.users import get_user_by_username, set_user_password

    await init_db()
    try:
        async with AsyncSessionLocal() as db:
            user = await get_user_by_username(db, username)
            if user is None:
                print(f"User '{username}' does not exist.", file=sys.stderr)
                return 1
            if not user.is_active:
                # The reset is still useful: an operator usually reactivates
                # the account right after, and refusing here would leave no
                # way to fix a locked out administrator.
                print(
                    f"Warning: user '{username}' is inactive; "
                    "the new password will not allow a login until the "
                    "account is activated.",
                    file=sys.stderr,
                )

            await set_user_password(db, user, password)
            print(f"Password updated for {username}")
            return 0
    finally:
        await engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(prog="bidar", description="Bidar admin CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_admin = subparsers.add_parser(
        "create-admin", help="Create an administrative account"
    )
    create_admin.add_argument("--username", required=True)
    create_admin.add_argument("--email", required=True)
    create_admin.add_argument("--full-name", default=None)
    create_admin.add_argument(
        "--role",
        default=SUPER_ADMIN_ROLE,
        choices=list(VALID_ROLES),
        help="Role to assign (default: super_admin)",
    )
    create_admin.add_argument(
        "--non-interactive",
        action="store_true",
        help=f"Fail instead of prompting when {PASSWORD_ENV_VAR} is unset",
    )

    reset_password = subparsers.add_parser(
        "reset-password",
        help="Set a new password for an existing account",
        description=(
            "Set a new password for an existing account. The password is read "
            f"from {NEW_PASSWORD_ENV_VAR} or from an interactive prompt, never "
            "from the command line. Tokens issued before the reset stay valid "
            "until they expire, because the service keeps no revocation store."
        ),
    )
    reset_password.add_argument("--username", required=True)
    reset_password.add_argument(
        "--non-interactive",
        action="store_true",
        help=f"Fail instead of prompting when {NEW_PASSWORD_ENV_VAR} is unset",
    )
    return parser


def main(argv: Optional[list] = None) -> int:
    """CLI entry point."""
    args = build_parser().parse_args(argv)

    if args.command == "create-admin":
        password = _read_password(args.non_interactive)
        _validate_password(password)
        return asyncio.run(
            _create_admin(
                username=args.username,
                email=args.email,
                full_name=args.full_name,
                role=args.role,
                password=password,
            )
        )

    if args.command == "reset-password":
        password = _read_password(args.non_interactive, NEW_PASSWORD_ENV_VAR)
        _validate_password(password)
        return asyncio.run(_reset_password(username=args.username, password=password))

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

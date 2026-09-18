# --------------------------------------------------------------------------
# Password length rules shared by models, CRUD and the CLI
#
# This module must not import from src.models or src.crud so that it can be
# used by every layer without creating an import cycle.
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------

# bcrypt refuses to hash a password longer than 72 bytes. Silently truncating
# would make two different passwords that share a 72 byte prefix equivalent,
# so long passwords are rejected at the input boundary instead. Note that the
# limit is in bytes: a Hangul or emoji character costs three or four.
BCRYPT_MAX_PASSWORD_BYTES = 72

# Minimum length in characters, shared by the admin creation schema and the
# create-admin CLI so that the two cannot drift apart.
MIN_PASSWORD_LENGTH = 12


class PasswordTooLongError(ValueError):
    """Raised when a password exceeds what bcrypt can hash."""

    def __init__(self) -> None:
        """Build the error with the user facing message."""
        super().__init__(
            "Password must be at most "
            f"{BCRYPT_MAX_PASSWORD_BYTES} bytes when encoded as UTF-8. "
            "Non-ASCII characters take more than one byte each."
        )


def password_byte_length(password: str) -> int:
    """Return the UTF-8 byte length bcrypt will actually see."""
    return len(password.encode("utf-8"))


def is_password_length_supported(password: str) -> bool:
    """Return True when bcrypt can hash this password without truncation."""
    return password_byte_length(password) <= BCRYPT_MAX_PASSWORD_BYTES


def validate_password_length(password: str) -> str:
    """Return the password unchanged, or raise if bcrypt cannot hash it.

    Raises:
        PasswordTooLongError: If the UTF-8 encoding exceeds 72 bytes.
    """
    if not is_password_length_supported(password):
        raise PasswordTooLongError()
    return password

# --------------------------------------------------------------------------
# Configuration module
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import secrets
import warnings
from typing import Annotated, Any, List, Literal, Union

from pydantic import AnyUrl, BeforeValidator, computed_field, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing_extensions import Self

# Minimum length for an HS256 signing key. 32 bytes matches the digest size of
# SHA-256, which is the smallest key length that does not weaken the HMAC.
MIN_JWT_SECRET_LENGTH = 32

# Substrings that identify the example/placeholder secrets shipped in
# env.example, documentation and older deployments.
FORBIDDEN_SECRET_MARKERS = (
    "changethis",
    "change-this",
    "change-in-production",
    "change-me",
    "changeme",
    "your-super-secret",
    "your-secret-key",
    "secret-key-change",
    "example",
    "placeholder",
)

# Development-only fallback. The database name matches the real one
# (`bngdrasil`) so that a local run does not quietly point somewhere else.
DEV_DATABASE_URL = "postgresql://bnbong:password@postgres:5432/bngdrasil"


def parse_cors(v: Any) -> Union[List[str], str]:
    """Parse a comma separated origin list into a list of strings."""
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, (list, str)):
        return v
    raise ValueError(v)


def parse_str_list(v: Any) -> List[str]:
    """Parse a comma separated string (or a list) into a list of strings.

    An empty or whitespace-only value yields an empty list so that the caller
    can decide on a safe default instead of passing [""] to middleware.
    """
    if isinstance(v, str):
        return [item.strip() for item in v.split(",") if item.strip()]
    if isinstance(v, (list, tuple)):
        return [str(item).strip() for item in v if str(item).strip()]
    raise ValueError(v)


# NoDecode stops pydantic-settings from JSON-decoding the raw environment
# value before the validator sees the comma separated string.
StrList = Annotated[List[str], NoDecode, BeforeValidator(parse_str_list)]


class Settings(BaseSettings):
    """Project configuration.

    Values are read from the process environment first and from a local
    ``.env`` file as a fallback. In ``production`` the validator refuses to
    start with missing or example secrets.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    SECRET_KEY: str = secrets.token_urlsafe(32)
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    CLIENT_ORIGIN: str = ""

    BACKEND_CORS_ORIGINS: Annotated[
        Union[List[AnyUrl], str], NoDecode, BeforeValidator(parse_cors)
    ] = []

    # Server
    # bandit B104 (false positive): the service runs in a container behind
    # the gateway and must bind every interface to be reachable. Exposure is
    # limited by the host firewall and by TrustedHostMiddleware.
    HOST: str = "0.0.0.0"  # nosec B104
    PORT: int = 8001

    # Comma separated list of proxy addresses whose X-Forwarded-For and
    # X-Forwarded-Proto headers uvicorn is allowed to trust, or "*" to trust
    # every peer. Only the immediate peer is checked, so this must list the
    # reverse proxy in front of the service (VM1 Nginx in this deployment) and
    # nothing else. Trusting "*" while the port is reachable directly lets a
    # client forge its own source address.
    FORWARDED_ALLOW_IPS: str = "127.0.0.1"

    # Security. Both are comma separated in the environment and become lists
    # that are handed to TrustedHostMiddleware / CORSMiddleware directly.
    # The default is empty so that "not configured" can be told apart from an
    # explicit wildcard: production refuses empty, development falls back to
    # the wildcard.
    ALLOWED_HOSTS: StrList = []
    ALLOWED_ORIGINS: StrList = []

    # JWT Settings. No usable default: production refuses an empty or example
    # key, development falls back to an ephemeral random key.
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Brute-force mitigation for POST /auth/token only. This is an in-process
    # counter, so it is per worker and resets on restart. It is a mitigation,
    # not a quota; a shared edge limiter remains the durable control.
    # The limiter keys on request.client.host, which only distinguishes real
    # callers when FORWARDED_ALLOW_IPS names the reverse proxy.
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10

    # Database
    DATABASE_URL: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> List[str]:
        """Return every configured CORS origin without a trailing slash."""
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.CLIENT_ORIGIN
        ]

    PROJECT_NAME: str = "bidar"

    @property
    def is_production(self) -> bool:
        """Return True when the service runs with production hardening."""
        return self.ENVIRONMENT == "production"

    def _check_default_secret(self, var_name: str, value: Union[str, None]) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "development":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    def _validate_jwt_secret(self) -> None:
        value = self.JWT_SECRET_KEY.strip()

        if not self.is_production:
            if not value:
                # Development and test runs without an explicit key get a
                # throwaway key. Tokens do not survive a restart.
                self.JWT_SECRET_KEY = secrets.token_urlsafe(MIN_JWT_SECRET_LENGTH)
            return

        if not value:
            raise ValueError(
                "JWT_SECRET_KEY must be set in production. "
                "Provide a random value of at least "
                f"{MIN_JWT_SECRET_LENGTH} characters."
            )
        if len(value) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                "JWT_SECRET_KEY is too short for production: "
                f"{len(value)} characters, minimum is {MIN_JWT_SECRET_LENGTH}."
            )
        lowered = value.lower()
        for marker in FORBIDDEN_SECRET_MARKERS:
            if marker in lowered:
                raise ValueError(
                    "JWT_SECRET_KEY looks like an example value "
                    f"(contains '{marker}'). Generate a new random secret."
                )

    def _validate_host_lists(self) -> None:
        """Require explicit host and origin lists in production.

        Both an empty value and a wildcard are refused: a wildcard
        ALLOWED_HOSTS makes TrustedHostMiddleware accept any Host header, and
        a wildcard ALLOWED_ORIGINS lets any site call this API from a browser.
        This matches Bifrost, and the Baedalus env.template already supplies
        explicit lists.
        """
        for name, example in (
            ("ALLOWED_HOSTS", "api.bnbong.com,auth-server,localhost"),
            ("ALLOWED_ORIGINS", "https://admin.bnbong.com,https://bnbong.com"),
        ):
            value: List[str] = getattr(self, name)

            if not value:
                if self.is_production:
                    raise ValueError(
                        f"{name} must be set in production. Provide a comma "
                        f"separated list, for example {name}={example}."
                    )
                setattr(self, name, ["*"])
                continue

            if self.is_production and "*" in value:
                raise ValueError(
                    f"{name} must not contain '*' in production. List the "
                    f"real values, for example {name}={example}."
                )

    def _validate_database_url(self) -> None:
        if self.DATABASE_URL.strip():
            return
        if self.is_production:
            raise ValueError("DATABASE_URL must be set in production.")
        self.DATABASE_URL = DEV_DATABASE_URL

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._validate_jwt_secret()
        self._validate_database_url()
        self._validate_host_lists()

        return self


settings = Settings()

# --------------------------------------------------------------------------
# Configuration module
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import os
import secrets
import warnings
from typing import Annotated, Any, List, Literal, Union

from pydantic import AnyUrl, BeforeValidator, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> Union[List[str], str]:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, (list, str)):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    """Default project configuraion module

    This base module configures your project SECRET_KEY, CORS origins and project name

    **Add your project configurations below**


    For more information, please refer to the following link:

    https://fastapi.tiangolo.com/advanced/settings/?h=config
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    SECRET_KEY: str = secrets.token_urlsafe(32)
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    CLIENT_ORIGIN: str = ""

    BACKEND_CORS_ORIGINS: Annotated[
        Union[List[AnyUrl], str], BeforeValidator(parse_cors)
    ] = []

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8001"))

    # Security
    ALLOWED_HOSTS: str = os.getenv("ALLOWED_HOSTS", "*")
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")

    # JWT Settings
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", "your-secret-key-change-in-production"
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/1")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://bnbong:password@postgres:5432/bnbong"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> List[str]:
        return [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS] + [
            self.CLIENT_ORIGIN
        ]

    PROJECT_NAME: str = "bidar"

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

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)

        return self


settings = Settings()

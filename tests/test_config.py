# --------------------------------------------------------------------------
# Tests for configuration settings
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.core.config import DEV_DATABASE_URL, Settings

# A key long enough for HS256 that does not contain any example marker.
STRONG_TEST_KEY = "Tn6qzE2sWvJ4hLpR9xYb3MdKgC7uAfZq"


def build_settings(**env: str) -> Settings:
    """Build Settings from an explicit environment, ignoring any local .env."""
    with patch.dict(os.environ, env, clear=True):
        return Settings(_env_file=None)  # type: ignore[call-arg]


class TestSettings:
    """Test cases for Settings class."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = build_settings()
        assert settings.ENVIRONMENT == "development"
        assert settings.DEBUG is False
        assert settings.LOG_LEVEL == "INFO"
        assert settings.HOST == "0.0.0.0"
        assert settings.PORT == 8001
        assert settings.ALLOWED_HOSTS == ["*"]
        assert settings.ALLOWED_ORIGINS == ["*"]
        assert settings.JWT_ALGORITHM == "HS256"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7
        assert settings.LOGIN_RATE_LIMIT_PER_MINUTE == 10
        assert settings.FORWARDED_ALLOW_IPS == "127.0.0.1"

    def test_development_generates_ephemeral_jwt_key(self) -> None:
        """Development without an explicit key gets a random one."""
        settings = build_settings()
        assert len(settings.JWT_SECRET_KEY) >= 32
        other = build_settings()
        assert settings.JWT_SECRET_KEY != other.JWT_SECRET_KEY

    def test_development_database_url_fallback(self) -> None:
        """Development without DATABASE_URL falls back to the local default."""
        settings = build_settings()
        assert settings.DATABASE_URL == DEV_DATABASE_URL

    def test_environment_variables(self) -> None:
        """Test settings loaded from environment variables."""
        settings = build_settings(
            ENVIRONMENT="production",
            DEBUG="true",
            LOG_LEVEL="DEBUG",
            HOST="127.0.0.1",
            PORT="9000",
            JWT_SECRET_KEY=STRONG_TEST_KEY,
            JWT_ALGORITHM="HS512",
            ACCESS_TOKEN_EXPIRE_MINUTES="60",
            REFRESH_TOKEN_EXPIRE_DAYS="30",
            DATABASE_URL="postgresql://test:test@localhost:5432/test",
            ALLOWED_HOSTS="localhost,127.0.0.1",
            ALLOWED_ORIGINS="https://example.com,https://api.example.com",
        )

        assert settings.ENVIRONMENT == "production"
        assert settings.DEBUG is True
        assert settings.LOG_LEVEL == "DEBUG"
        assert settings.HOST == "127.0.0.1"
        assert settings.PORT == 9000
        assert settings.JWT_SECRET_KEY == STRONG_TEST_KEY
        assert settings.JWT_ALGORITHM == "HS512"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 30
        assert settings.DATABASE_URL == "postgresql://test:test@localhost:5432/test"
        assert settings.ALLOWED_HOSTS == ["localhost", "127.0.0.1"]
        assert settings.ALLOWED_ORIGINS == [
            "https://example.com",
            "https://api.example.com",
        ]

    def test_forwarded_allow_ips_from_environment(self) -> None:
        """The trusted proxy list is read verbatim and handed to uvicorn."""
        assert (
            build_settings(FORWARDED_ALLOW_IPS="10.0.1.133").FORWARDED_ALLOW_IPS
            == "10.0.1.133"
        )
        assert (
            build_settings(
                FORWARDED_ALLOW_IPS="10.0.1.133, 127.0.0.1"
            ).FORWARDED_ALLOW_IPS
            == "10.0.1.133, 127.0.0.1"
        )
        assert build_settings(FORWARDED_ALLOW_IPS="*").FORWARDED_ALLOW_IPS == "*"

    def test_boolean_parsing(self) -> None:
        """Test boolean environment variable parsing."""
        assert build_settings(DEBUG="true").DEBUG is True
        assert build_settings(DEBUG="false").DEBUG is False
        assert build_settings(DEBUG="TRUE").DEBUG is True
        assert build_settings(DEBUG="FALSE").DEBUG is False

    def test_integer_parsing(self) -> None:
        """Test integer environment variable parsing."""
        assert build_settings(PORT="8080").PORT == 8080
        assert (
            build_settings(ACCESS_TOKEN_EXPIRE_MINUTES="45").ACCESS_TOKEN_EXPIRE_MINUTES
            == 45
        )

    def test_host_list_parsing(self) -> None:
        """Comma separated hosts and origins become lists."""
        settings = build_settings(
            ALLOWED_HOSTS="host1, host2 ,host3",
            ALLOWED_ORIGINS="https://site1.com,https://site2.com",
        )
        assert settings.ALLOWED_HOSTS == ["host1", "host2", "host3"]
        assert settings.ALLOWED_ORIGINS == [
            "https://site1.com",
            "https://site2.com",
        ]

    def test_single_item_string(self) -> None:
        """A single host stays a one item list."""
        assert build_settings(ALLOWED_HOSTS="singlehost").ALLOWED_HOSTS == [
            "singlehost"
        ]

    def test_empty_string_fallback(self) -> None:
        """An empty host list falls back to the wildcard instead of ['']."""
        assert build_settings(ALLOWED_HOSTS="").ALLOWED_HOSTS == ["*"]
        assert build_settings(ALLOWED_ORIGINS=" , ").ALLOWED_ORIGINS == ["*"]

    def test_settings_singleton(self) -> None:
        """Test that the module level settings instance is usable."""
        from src.core.config import settings

        assert isinstance(settings, Settings)
        assert settings.ENVIRONMENT in ["development", "test", "production"]


class TestProductionSecretValidation:
    """SEC-05: production refuses missing or example secrets."""

    @pytest.mark.parametrize(
        "secret",
        [
            "",
            "short-key",
            "your-super-secret-jwt-key-change-this-in-production",
            "your-secret-key-change-in-production",
            "changethis-changethis-changethis-changethis",
            "example-secret-key-for-documentation-only",
        ],
    )
    def test_production_rejects_weak_jwt_secret(self, secret: str) -> None:
        """A missing, short or example JWT key fails to start in production."""
        with pytest.raises(ValidationError) as exc_info:
            build_settings(
                ENVIRONMENT="production",
                JWT_SECRET_KEY=secret,
                DATABASE_URL="postgresql://u:p@db:5432/bngdrasil",
                ALLOWED_HOSTS="api.bnbong.com",
                ALLOWED_ORIGINS="https://admin.bnbong.com",
            )
        assert "JWT_SECRET_KEY" in str(exc_info.value)

    def test_production_requires_database_url(self) -> None:
        """A missing DATABASE_URL fails to start in production."""
        with pytest.raises(ValidationError) as exc_info:
            build_settings(
                ENVIRONMENT="production",
                JWT_SECRET_KEY=STRONG_TEST_KEY,
                ALLOWED_HOSTS="api.bnbong.com",
                ALLOWED_ORIGINS="https://admin.bnbong.com",
            )
        assert "DATABASE_URL" in str(exc_info.value)

    def test_production_accepts_strong_secret(self) -> None:
        """A complete production configuration starts normally."""
        settings = build_settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY=STRONG_TEST_KEY,
            DATABASE_URL="postgresql://u:p@db:5432/bngdrasil",
            ALLOWED_HOSTS="api.bnbong.com,auth-server,localhost",
            ALLOWED_ORIGINS="https://admin.bnbong.com",
        )
        assert settings.is_production is True
        assert settings.JWT_SECRET_KEY == STRONG_TEST_KEY

    def test_non_production_allows_weak_secret(self) -> None:
        """Development and test keep working with a short explicit key."""
        settings = build_settings(ENVIRONMENT="test", JWT_SECRET_KEY="short-test-key")
        assert settings.JWT_SECRET_KEY == "short-test-key"

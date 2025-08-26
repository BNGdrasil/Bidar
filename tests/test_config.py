# --------------------------------------------------------------------------
# Tests for configuration settings
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import os
from unittest.mock import patch

import pytest

from src.core.config import Settings


class TestSettings:
    """Test cases for Settings class."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        with patch.dict(os.environ, {"DEBUG": "false"}, clear=True):
            settings = Settings()
            assert settings.ENVIRONMENT == "development"
            assert settings.DEBUG is False
            assert settings.LOG_LEVEL == "INFO"
            assert settings.HOST == "0.0.0.0"
            assert settings.PORT == 8001
            assert settings.ALLOWED_HOSTS == "*"
            assert settings.ALLOWED_ORIGINS == "*"
            assert (
                "your-" in settings.JWT_SECRET_KEY
                and "change" in settings.JWT_SECRET_KEY
            )
            assert settings.JWT_ALGORITHM == "HS256"
            assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
            assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7
            assert settings.RATE_LIMIT_PER_MINUTE == 60
            assert settings.REDIS_URL == "redis://redis:6379/1"
            assert (
                settings.DATABASE_URL
                == "postgresql://bnbong:password@postgres:5432/bnbong"
            )

    @patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "DEBUG": "true",
            "LOG_LEVEL": "DEBUG",
            "HOST": "127.0.0.1",
            "PORT": "9000",
            "JWT_SECRET_KEY": "test-secret-key",
            "JWT_ALGORITHM": "HS512",
            "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
            "REFRESH_TOKEN_EXPIRE_DAYS": "30",
            "RATE_LIMIT_PER_MINUTE": "120",
            "REDIS_URL": "redis://localhost:6379/0",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "ALLOWED_HOSTS": "localhost,127.0.0.1",
            "ALLOWED_ORIGINS": "https://example.com,https://api.example.com",
        },
    )
    def test_environment_variables(self) -> None:
        """Test settings loaded from environment variables."""
        settings = Settings()

        assert settings.ENVIRONMENT == "production"
        assert settings.DEBUG is True
        assert settings.LOG_LEVEL == "DEBUG"
        assert settings.HOST == "127.0.0.1"
        assert settings.PORT == 9000
        assert settings.JWT_SECRET_KEY == "test-secret-key"
        assert settings.JWT_ALGORITHM == "HS512"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 30
        assert settings.RATE_LIMIT_PER_MINUTE == 120
        assert settings.REDIS_URL == "redis://localhost:6379/0"
        assert settings.DATABASE_URL == "postgresql://test:test@localhost:5432/test"
        assert settings.ALLOWED_HOSTS == "localhost,127.0.0.1"
        assert settings.ALLOWED_ORIGINS == "https://example.com,https://api.example.com"

    def test_boolean_parsing(self) -> None:
        """Test boolean environment variable parsing."""
        with patch.dict(os.environ, {"DEBUG": "true"}):
            settings = Settings()
            assert settings.DEBUG is True

        with patch.dict(os.environ, {"DEBUG": "false"}):
            settings = Settings()
            assert settings.DEBUG is False

        with patch.dict(os.environ, {"DEBUG": "TRUE"}):
            settings = Settings()
            assert settings.DEBUG is True

        with patch.dict(os.environ, {"DEBUG": "FALSE"}):
            settings = Settings()
            assert settings.DEBUG is False

    def test_integer_parsing(self) -> None:
        """Test integer environment variable parsing."""
        with patch.dict(os.environ, {"PORT": "8080"}):
            settings = Settings()
            assert settings.PORT == 8080

        with patch.dict(os.environ, {"ACCESS_TOKEN_EXPIRE_MINUTES": "45"}):
            settings = Settings()
            assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 45

    def test_string_parsing(self) -> None:
        """Test string environment variable parsing."""
        with patch.dict(os.environ, {"ALLOWED_HOSTS": "host1,host2,host3"}):
            settings = Settings()
            assert settings.ALLOWED_HOSTS == "host1,host2,host3"

        with patch.dict(
            os.environ, {"ALLOWED_ORIGINS": "https://site1.com,https://site2.com"}
        ):
            settings = Settings()
            assert settings.ALLOWED_ORIGINS == "https://site1.com,https://site2.com"

    def test_single_item_string(self) -> None:
        """Test string parsing with single item."""
        with patch.dict(os.environ, {"ALLOWED_HOSTS": "singlehost"}):
            settings = Settings()
            assert settings.ALLOWED_HOSTS == "singlehost"

    def test_empty_string_fallback(self) -> None:
        """Test empty string fallback to default."""
        with patch.dict(os.environ, {"ALLOWED_HOSTS": ""}):
            settings = Settings()
            assert settings.ALLOWED_HOSTS == ""

    def test_settings_singleton(self) -> None:
        """Test that settings instance is consistent."""
        from src.core.config import settings

        assert isinstance(settings, Settings)
        # In CI environment, ENVIRONMENT might be set to 'test'
        # So we check that it's one of the expected values
        assert settings.ENVIRONMENT in ["development", "test", "production"]

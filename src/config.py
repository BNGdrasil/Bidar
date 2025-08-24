# --------------------------------------------------------------------------
# Configuration settings for the Auth Server
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
import os
from typing import List


class Settings:
    """Application settings."""

    def __init__(self) -> None:
        """Initialize application settings."""
        # Environment
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

        # Server
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", "8001"))

        # Security
        self.ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")
        self.ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

        # JWT Settings
        self.JWT_SECRET_KEY = os.getenv(
            "JWT_SECRET_KEY", "your-secret-key-change-in-production"
        )
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
        )
        self.REFRESH_TOKEN_EXPIRE_DAYS = int(
            os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
        )

        # Rate Limiting
        self.RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

        # Redis
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")

        # Database
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL", "postgresql://bnbong:password@postgres:5432/bnbong"
        )


settings = Settings()

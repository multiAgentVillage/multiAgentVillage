"""Configuration edge cases that affect local/Compose parity."""
import pytest
from pydantic import ValidationError

from app.config import Settings


def test_empty_url_falls_back_to_component_fields():
    settings = Settings(
        _env_file=None, database_url="", postgres_host="postgres",
        postgres_user="campus", postgres_db="campus", postgres_password="p@ss:/?#%",
    )
    assert settings.sqlalchemy_url.drivername == "postgresql+asyncpg"
    assert settings.sqlalchemy_url.host == "postgres"
    assert settings.sqlalchemy_url.password == "p@ss:/?#%"


def test_explicit_url_requires_asyncpg():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql://campus:password@localhost/campus")

"""Centralized configuration for Stockflow.

Secrets are loaded from environment variables. Copy .env.example to .env
for local development; never commit the populated .env file.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        required = ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise RuntimeError(
                "Missing database environment variables: " + ", ".join(missing)
            )
        return cls(
            host=os.environ["PGHOST"],
            port=int(os.getenv("PGPORT", "5432")),
            database=os.environ["PGDATABASE"],
            user=os.environ["PGUSER"],
            password=os.environ["PGPASSWORD"],
        )

    @property
    def sqlalchemy_url(self) -> str:
        from sqlalchemy.engine import URL
        return URL.create(
            "postgresql+psycopg2",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
        ).render_as_string(hide_password=False)

    @property
    def psycopg2_kwargs(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
        }

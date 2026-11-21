"""Centralized environment-backed configuration for Stockflow."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        # Load local .env values without overriding explicitly exported variables.
        load_dotenv()
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
    def psycopg2_kwargs(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
        }

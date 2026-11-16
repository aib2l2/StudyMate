import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    mode: str = "demo"
    database: str = ""
    booking_ttl: int = 900
    worker_enabled: bool = True
    commission_percent: int = 15

    def __post_init__(self):
        if self.mode == "live":
            object.__setattr__(self, "mode", "site")
        if self.mode not in {"demo", "site"}:
            raise ValueError("APP_MODE must be demo or site")
        if not 0 <= self.commission_percent <= 100:
            raise ValueError("COMMISSION_PERCENT must be between 0 and 100")
        path = Path(self.database or ROOT / "data" / f"{self.mode}.sqlite3").resolve()
        if self.mode == "site" and "demo" in path.name.lower():
            raise ValueError("Site mode must never use a demo database")
        if self.mode == "demo" and "demo" not in path.name.lower():
            raise ValueError("Demo database filename must contain 'demo'")
        object.__setattr__(self, "database", str(path))

    @classmethod
    def load(cls):
        load_dotenv(ROOT / ".env")
        return cls(
            mode=os.getenv("APP_MODE", "demo"),
            database=os.getenv("DATABASE_PATH", ""),
            worker_enabled=os.getenv("WORKER_ENABLED", "1") == "1",
            commission_percent=int(os.getenv("COMMISSION_PERCENT", "15")),
        )

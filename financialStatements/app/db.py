from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "statements.db"

ENGINE = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, future=True)


def get_session() -> Generator:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.utcnow()


def ensure_schema() -> None:
    with ENGINE.begin() as conn:
        result = conn.execute(text("PRAGMA table_info(transactions)"))
        existing = {row[1] for row in result.fetchall()}

        columns = {
            "transfer_group_id": "VARCHAR(64)",
            "transfer_from_currency": "VARCHAR(8)",
            "transfer_to_currency": "VARCHAR(8)",
            "fx_rate_applied": "FLOAT",
            "fx_rate_official": "FLOAT",
            "fx_loss_ron": "FLOAT",
            "amount_override": "NUMERIC(18, 2)",
        }

        for column, col_type in columns.items():
            if column not in existing:
                conn.execute(text(f"ALTER TABLE transactions ADD COLUMN {column} {col_type}"))

        result = conn.execute(text("PRAGMA table_info(statements)"))
        existing_statements = {row[1] for row in result.fetchall()}
        if "include_in_metrics" not in existing_statements:
            conn.execute(text("ALTER TABLE statements ADD COLUMN include_in_metrics BOOLEAN DEFAULT 1"))

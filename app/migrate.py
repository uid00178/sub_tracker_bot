import asyncio
from sqlalchemy import text

from app.db import engine
from app.models import Base

EVENTS_DDL = [
    """
    CREATE TABLE IF NOT EXISTS events (
      id BIGSERIAL PRIMARY KEY,
      user_id BIGINT NOT NULL,
      event_name TEXT NOT NULL,
      ts_utc TIMESTAMPTZ NOT NULL DEFAULT now(),
      props JSONB NOT NULL DEFAULT '{}'::jsonb
    );
    """,
    "CREATE INDEX IF NOT EXISTS ix_events_ts ON events (ts_utc);",
    "CREATE INDEX IF NOT EXISTS ix_events_user ON events (user_id);",
    "CREATE INDEX IF NOT EXISTS ix_events_name_ts ON events (event_name, ts_utc);",
]

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in EVENTS_DDL:
            await conn.execute(text(stmt))

if __name__ == "__main__":
    asyncio.run(main())

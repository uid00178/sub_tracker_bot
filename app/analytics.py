import json
from typing import Any, Dict, Optional

from sqlalchemy import text
from app.db import engine


async def track_event(user_id: int, event_name: str, props: Optional[Dict[str, Any]] = None) -> None:
    props = props or {}

    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO events (user_id, event_name, props)
                VALUES (:user_id, :event_name, CAST(:props AS jsonb))
            """),
            {
                "user_id": user_id,
                "event_name": event_name,
                "props": json.dumps(props),
            },
        )

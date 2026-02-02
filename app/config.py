import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    database_url: str
    default_tz: str
    reminder_hour: int

    mode: str  # polling | webhook
    webhook_base: str
    webhook_path: str
    webhook_secret: str
    web_server_host: str
    web_server_port: int

    test_reminders: bool
    test_d3_minutes: int
    test_d1_minutes: int

def load_config() -> Config:
    return Config(
        bot_token=os.environ["BOT_TOKEN"],
        database_url=os.environ["DATABASE_URL"],
        default_tz=os.getenv("DEFAULT_TZ", "Europe/Vilnius"),
        reminder_hour=int(os.getenv("REMINDER_HOUR", "10")),

        mode=os.getenv("MODE", "polling").strip().lower(),
        webhook_base=os.getenv("WEBHOOK_BASE", "").strip(),
        webhook_path=os.getenv("WEBHOOK_PATH", "/tg/webhook").strip(),
        webhook_secret=os.getenv("WEBHOOK_SECRET", "").strip(),
        web_server_host=os.getenv("WEB_SERVER_HOST", "0.0.0.0").strip(),
        web_server_port=int(os.getenv("WEB_SERVER_PORT", "8080")),

        test_reminders=os.getenv("TEST_REMINDERS", "0") == "1",
        test_d3_minutes=int(os.getenv("TEST_D3_MINUTES", "3")),
        test_d1_minutes=int(os.getenv("TEST_D1_MINUTES", "1")),
    )

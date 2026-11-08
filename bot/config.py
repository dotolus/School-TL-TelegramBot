from dataclasses import dataclass
from typing import Mapping

DEFAULT_CLAUDE_MODEL = "claude-sonnet-5-5"

_REQUIRED_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "ANTHROPIC_API_KEY",
    "SCHOOL_TL_BASE_URL",
    "SCHOOL_TL_SCHOOL",
    "SCHOOL_TL_PERIOD",
    "SCHOOL_TL_CLASS",
    "SCHOOL_TL_ADMIN_PASSWORD",
    "ALLOWED_TELEGRAM_USER_IDS",
)


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    anthropic_api_key: str
    claude_model: str
    school_tl_base_url: str
    school: str
    period: str
    school_class: str
    admin_password: str
    allowed_user_ids: frozenset[int]


def _parse_allowed_user_ids(raw: str) -> frozenset[int]:
    ids = []
    for entry in raw.split(","):
        entry = entry.strip()
        try:
            ids.append(int(entry))
        except ValueError:
            raise ConfigError(
                f"ALLOWED_TELEGRAM_USER_IDS contains a non-integer entry: {entry!r}"
            ) from None
    return frozenset(ids)


def load_config(env: Mapping[str, str]) -> Config:
    for key in _REQUIRED_KEYS:
        if key not in env:
            raise ConfigError(f"Missing required environment variable: {key}")

    return Config(
        telegram_bot_token=env["TELEGRAM_BOT_TOKEN"],
        anthropic_api_key=env["ANTHROPIC_API_KEY"],
        claude_model=env.get("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL),
        school_tl_base_url=env["SCHOOL_TL_BASE_URL"],
        school=env["SCHOOL_TL_SCHOOL"],
        period=env["SCHOOL_TL_PERIOD"],
        school_class=env["SCHOOL_TL_CLASS"],
        admin_password=env["SCHOOL_TL_ADMIN_PASSWORD"],
        allowed_user_ids=_parse_allowed_user_ids(env["ALLOWED_TELEGRAM_USER_IDS"]),
    )

import pytest

from bot.config import ConfigError, load_config

BASE_ENV = {
    "TELEGRAM_BOT_TOKEN": "tg-token",
    "ANTHROPIC_API_KEY": "anthropic-key",
    "SCHOOL_TL_BASE_URL": "https://reutl.vercel.app",
    "SCHOOL_TL_SCHOOL": "reut",
    "SCHOOL_TL_PERIOD": "2026-2027",
    "SCHOOL_TL_CLASS": "e4",
    "SCHOOL_TL_ADMIN_PASSWORD": "secret",
    "ALLOWED_TELEGRAM_USER_IDS": "111,222",
}


def test_load_config_reads_all_required_fields():
    env = {
        "TELEGRAM_BOT_TOKEN": "tg-token",
        "ANTHROPIC_API_KEY": "anthropic-key",
        "SCHOOL_TL_BASE_URL": "https://reutl.vercel.app",
        "SCHOOL_TL_SCHOOL": "reut",
        "SCHOOL_TL_PERIOD": "2026-2027",
        "SCHOOL_TL_CLASS": "e4",
        "SCHOOL_TL_ADMIN_PASSWORD": "secret",
        "ALLOWED_TELEGRAM_USER_IDS": "111,222",
    }
    config = load_config(env)
    assert config.school_tl_base_url == "https://reutl.vercel.app"
    assert config.allowed_user_ids == frozenset({111, 222})
    assert config.claude_model == "claude-sonnet-5-5"  # default, not in env


def test_load_config_honors_explicit_claude_model():
    env = {**BASE_ENV, "CLAUDE_MODEL": "claude-opus-5-5"}
    assert load_config(env).claude_model == "claude-opus-5-5"


def test_load_config_raises_on_missing_required_var():
    env = {k: v for k, v in BASE_ENV.items() if k != "SCHOOL_TL_ADMIN_PASSWORD"}
    with pytest.raises(ConfigError, match="SCHOOL_TL_ADMIN_PASSWORD"):
        load_config(env)


def test_load_config_raises_on_non_integer_user_id():
    env = {**BASE_ENV, "ALLOWED_TELEGRAM_USER_IDS": "111,not-a-number"}
    with pytest.raises(ConfigError, match="ALLOWED_TELEGRAM_USER_IDS"):
        load_config(env)

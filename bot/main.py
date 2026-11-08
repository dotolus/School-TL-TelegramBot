import os

import anthropic
import httpx
from dotenv import load_dotenv

from bot.config import load_config
from bot.pending import PendingProposals
from bot.school_tl_client import SchoolTLClient
from bot.telegram_bot import build_application


def main() -> None:
    load_dotenv()
    config = load_config(os.environ)

    http_client = httpx.AsyncClient()
    claude_client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    school_tl_client = SchoolTLClient(
        http_client,
        base_url=config.school_tl_base_url,
        school=config.school,
        period=config.period,
        school_class=config.school_class,
        admin_password=config.admin_password,
    )
    pending = PendingProposals()

    application = build_application(config, school_tl_client, claude_client, pending)
    application.run_polling()


if __name__ == "__main__":
    main()

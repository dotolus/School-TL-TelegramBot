from unittest.mock import Mock, patch

import bot.main


def test_main_loads_dotenv_before_reading_config():
    call_order = []

    with (
        patch("bot.main.load_dotenv", side_effect=lambda: call_order.append("load_dotenv")) as mock_load_dotenv,
        patch(
            "bot.main.load_config",
            side_effect=lambda env: call_order.append("load_config") or Mock(),
        ) as mock_load_config,
        patch("bot.main.httpx.AsyncClient"),
        patch("bot.main.anthropic.AsyncAnthropic"),
        patch("bot.main.SchoolTLClient"),
        patch("bot.main.PendingProposals"),
        patch("bot.main.build_application") as mock_build_application,
    ):
        bot.main.main()

    mock_load_dotenv.assert_called_once()
    mock_load_config.assert_called_once()
    assert call_order == ["load_dotenv", "load_config"]
    mock_build_application.return_value.run_polling.assert_called_once()

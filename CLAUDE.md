# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

A Python Telegram bot (package: `bot/`) that answers free-form Hebrew questions about the School-TL class timeline and lets the owner create new timeline items from free-form Hebrew, confirmed before any write. Design: `docs/superpowers/specs/2026-11-08-telegram-bot-design.md`. Implementation plan and task-by-task record: `docs/superpowers/plans/2026-11-08-telegram-bot.md`.

The `accounts/`, `config/`, `core/`, `delivery/` directories (plus `.venv/`) at the repo root are unrelated leftovers (stray `__pycache__`/a Django venv from a different, sibling project) — not part of this bot. Don't mistake their presence for real code belonging here.

**Resolved:** an earlier divergent exploration (a Django "school atmosphere survey" platform in a separate sibling repo/worktree) was found and explicitly rejected by the user ("there is no need for a survey") — not relevant to this bot.

An MCP server, `codebase-memory-mcp`, is configured in `.mcp.json` at the repo root.

## Commands

First time: `python -m venv .venv-bot` (3.11+; this project was developed against 3.12 — on Windows, if the default `python` resolves to a newer interpreter whose async ecosystem libraries lag behind, use `py -3.12 -m venv .venv-bot` instead), then `.venv-bot/Scripts/python.exe -m pip install -r requirements-dev.txt` (Windows; `.venv-bot/bin/python` on macOS/Linux).

- Run the full test suite: `.venv-bot/Scripts/python.exe -m pytest -v`
- Run one file: `.venv-bot/Scripts/python.exe -m pytest tests/test_school_tl_client.py -v`
- Run one test: `.venv-bot/Scripts/python.exe -m pytest tests/test_school_tl_client.py -v -k test_get_timeline_returns_items`
- Run the bot: copy `.env.example` to `.env`, fill in the secrets, then `.venv-bot/Scripts/python.exe -m bot.main` (long-polling; no webhook, no public endpoint needed).
- No linter is configured yet — the pre-commit lint hook (`.claude/settings.json`) currently no-ops for this stack.

## Architecture

- `bot/config.py` — `load_config(env)` reads all required settings (Telegram token, Anthropic key, School-TL base URL/dataset/admin password, the Telegram user allow-list) from environment variables into a `Config`.
- `bot/school_tl_client.py` — `SchoolTLClient` talks to School-TL's real API: `GET .../timeline` to read, `POST .../timeline/items` to create (never edit/delete — out of scope, see the design doc's non-goals). On a `401`, it logs in once (`POST /api/auth/login`, shared admin password) and retries once, relying on `httpx`'s own cookie jar for the session.
- `bot/claude_assistant.py` — the only place that talks to the Claude API. `classify_message` uses tool-use to classify an incoming Hebrew message as a query, a new-item proposal (with extracted fields), or a declined edit request. `answer_query` composes the Hebrew answer to a query from the live timeline data.
- `bot/formatting.py` / `bot/pending.py` — `format_item_summary` renders the Hebrew confirmation text for a proposed item; `PendingProposals` is the per-chat in-memory store between "here's what I understood" and the user tapping confirm/cancel.
- `bot/telegram_bot.py` — `handle_text_message` and `handle_confirmation_callback` wire the above together; collaborators are read from `context.bot_data` (not imported directly) so handlers stay unit-testable without a live Telegram connection. `build_application` assembles the real `telegram.ext.Application`.
- `bot/main.py` — the only entrypoint; constructs real clients from `Config` and calls `run_polling()`.

Every write to School-TL is preceded by an explicit user confirmation — there is no code path that calls `create_item` without it. See the design doc for the full rationale, including why editing existing items isn't supported yet.

## Commit messages

When committing and pushing, write a meaningful commit message that covers both:
- **Business/why**: what user-facing or product problem this addresses, or why the change matters
- **Technical/what**: the concrete implementation change made

Keep it concise (a short summary line, plus 1-3 bullets if needed) — not a changelog dump.

## Available skills tracking

`user-available-skills.md` is an append-only log of skills available for use in this project. Whenever a new skill is added/installed/used for the first time, append it there (name + one-line description). Never remove an entry, even after that skill is no longer used.

## DevOps guidelines

`devops-guidelines.md` tracks DevOps/CI-CD/release requirements (branch policy, pipelines, deployments, infra, environments, secrets). Whenever a requirement or decision touches this domain, update that file to reflect it.

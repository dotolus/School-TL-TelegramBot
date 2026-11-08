# School-TL Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python Telegram bot that answers free-form Hebrew questions about the School-TL class timeline and lets the owner create new timeline items from free-form Hebrew, with a confirm step before any write.

**Architecture:** A single long-polling `python-telegram-bot` process. Each incoming message goes through an allow-list check, then one Claude API tool-use call that classifies it as a query, a new-item proposal, or a declined edit request. Queries read live from School-TL's `GET .../timeline` and get a Claude-composed Hebrew answer; proposals are held in memory and only written to School-TL (`POST .../timeline/items`, authenticated via the shared admin login) after the user taps an inline "confirm" button.

**Tech Stack:** Python 3.11+, `python-telegram-bot` (async, long-polling), `httpx.AsyncClient` (School-TL HTTP calls), `anthropic` SDK (`AsyncAnthropic`), `pytest` + `pytest-asyncio` + `respx` for tests.

**Spec:** `docs/superpowers/specs/2026-11-08-telegram-bot-design.md`

## Global Constraints

- Query source is `GET /api/{school}/{period}/{class}/timeline` only — never `.../events`.
- Write path is `POST /api/{school}/{period}/{class}/timeline/items` only. No `PUT`/edit/delete of existing items anywhere in this codebase (v1 non-goal).
- Write auth is the shared `ADMIN_PASSWORD` via `POST /api/auth/login` with body `{"password": "<value>"}`, cookie-based session. Any `401` from a dataset-scoped call means "log in (again) and retry the request once."
- All natural-language understanding and all Hebrew reply text are produced by the Claude API. No regex/keyword parsing of the user's Hebrew message anywhere.
- Every write is preceded by an explicit user confirmation (inline Yes/Cancel); there is no code path that calls `POST .../timeline/items` without that confirmation having happened first.
- Secrets (`TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`, `SCHOOL_TL_ADMIN_PASSWORD`) come only from environment variables, never hardcoded or committed.
- Long-polling only — no webhook, no public HTTP endpoint.

## Review Focus

- An unauthorized Telegram user id sends a message — must be rejected with a reply, never silently processed and never a crash. (Task 6)
- School-TL rejects a proposed item with `400` (bad data Claude extracted) — the user must see a clear Hebrew failure, not a crash or a silently dropped item. (Task 2, Task 6)
- A message asks to edit, move, or delete an existing item — must route to the decline path, never get misfired as a new-item creation (a silent duplicate) or as a query. (Task 3, Task 6)
- The timeline has zero items (a fresh/empty dataset) — a query must get a sensible "nothing scheduled" answer, not a crash or a hallucinated item. (Task 4)
- A second new-item proposal arrives while an earlier one for the same chat is still unconfirmed — the newer proposal must cleanly replace the pending one, and confirming must apply only the latest, never both or a corrupted merge. (Task 6)

---

## File Structure

- `bot/config.py` — env var loading → `Config`.
- `bot/school_tl_client.py` — `SchoolTLClient`, `SchoolTLError`.
- `bot/claude_assistant.py` — `classify_message`, `answer_query`, tool schemas.
- `bot/formatting.py` — `format_item_summary`.
- `bot/pending.py` — `PendingProposals`.
- `bot/telegram_bot.py` — handlers, `build_application`.
- `bot/main.py` — entrypoint, wires everything, `run_polling()`.
- `tests/` mirrors each module above.
- `requirements.txt` (runtime), `requirements-dev.txt` (test-only), `.env.example`.

### Task 1: Config loading

**Files:**
- Create: `bot/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` (frozen dataclass: `telegram_bot_token: str`, `anthropic_api_key: str`, `claude_model: str`, `school_tl_base_url: str`, `school: str`, `period: str`, `school_class: str`, `admin_password: str`, `allowed_user_ids: frozenset[int]`); `ConfigError(Exception)`; `load_config(env: Mapping[str, str]) -> Config`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

Define `BASE_ENV` once at module scope in the test file with all required keys set (the same seven keys as the first test, minus `CLAUDE_MODEL`), and reuse it across the other three tests.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError` for `bot.config`.

- [ ] **Step 3: Implement `Config` and `load_config(env: Mapping[str, str]) -> Config` in `bot/config.py`**

Required keys: `TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`, `SCHOOL_TL_BASE_URL`, `SCHOOL_TL_SCHOOL`, `SCHOOL_TL_PERIOD`, `SCHOOL_TL_CLASS`, `SCHOOL_TL_ADMIN_PASSWORD`, `ALLOWED_TELEGRAM_USER_IDS`. A missing one raises `ConfigError` naming it. `CLAUDE_MODEL` is optional, defaulting to `"claude-sonnet-5-5"`. `ALLOWED_TELEGRAM_USER_IDS` is a comma-separated list of ints (trim whitespace per entry); a non-integer entry raises `ConfigError` naming the variable.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bot/config.py tests/test_config.py
git commit -m "feat: add environment-based config loader"
```

---

### Task 2: School-TL API client

**Files:**
- Create: `bot/school_tl_client.py`
- Test: `tests/test_school_tl_client.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (takes raw values, not `Config`, so it has no import-time dependency on Task 1).
- Produces: `SchoolTLError(Exception)` with attributes `status_code: int`, `message: str`; `SchoolTLClient.__init__(self, http_client: httpx.AsyncClient, base_url: str, school: str, period: str, school_class: str, admin_password: str)`; `async def get_timeline(self) -> list[dict]`; `async def create_item(self, item: dict) -> dict`.

- [ ] **Step 1: Write the failing tests**

Use `respx` to mock `https://fake.example/api/auth/login`, `https://fake.example/api/reut/2026-2027/e4/timeline` (GET), and `.../timeline/items` (POST), with a `SchoolTLClient` built from a real `httpx.AsyncClient(base_url="https://fake.example")`.

```python
@pytest.mark.asyncio
@respx.mock
async def test_get_timeline_returns_items():
    respx.get("https://fake.example/api/reut/2026-2027/e4/timeline").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "1", "title": "חג"}]})
    )
    client = make_client()
    assert await client.get_timeline() == [{"id": "1", "title": "חג"}]

@pytest.mark.asyncio
@respx.mock
async def test_create_item_logs_in_on_first_401_then_succeeds():
    login_route = respx.post("https://fake.example/api/auth/login").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    post_route = respx.post("https://fake.example/api/reut/2026-2027/e4/timeline/items").mock(
        side_effect=[httpx.Response(401, json={"error": "Authentication required"}),
                     httpx.Response(201, json={"id": "new-1", "title": "מבחן"})]
    )
    client = make_client()
    result = await client.create_item({"title": "מבחן"})
    assert result == {"id": "new-1", "title": "מבחן"}
    assert login_route.call_count == 1
    assert post_route.call_count == 2

@pytest.mark.asyncio
@respx.mock
async def test_create_item_raises_school_tl_error_on_validation_failure():
    respx.post("https://fake.example/api/reut/2026-2027/e4/timeline/items").mock(
        return_value=httpx.Response(400, json={"error": "title is required"})
    )
    client = make_client()
    with pytest.raises(SchoolTLError) as exc_info:
        await client.create_item({})
    assert exc_info.value.status_code == 400
    assert exc_info.value.message == "title is required"

@pytest.mark.asyncio
@respx.mock
async def test_login_sends_configured_password():
    route = respx.post("https://fake.example/api/auth/login").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    respx.post("https://fake.example/api/reut/2026-2027/e4/timeline/items").mock(
        side_effect=[httpx.Response(401, json={"error": "Authentication required"}),
                     httpx.Response(201, json={"id": "1"})]
    )
    client = make_client(admin_password="correct-secret")
    await client.create_item({"title": "x"})
    sent_body = json.loads(route.calls[0].request.content)
    assert sent_body == {"password": "correct-secret"}
```

Define a `make_client(admin_password="secret")` helper at module scope: builds `httpx.AsyncClient(base_url="https://fake.example")` and returns `SchoolTLClient(http_client, base_url="https://fake.example", school="reut", period="2026-2027", school_class="e4", admin_password=admin_password)`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_school_tl_client.py -v`
Expected: FAIL with `ModuleNotFoundError` for `bot.school_tl_client`.

- [ ] **Step 3: Implement `SchoolTLError` and `SchoolTLClient` in `bot/school_tl_client.py`**

Dataset path is `f"{school}/{period}/{school_class}"`; dataset-scoped URL is `f"{base_url}/api/{dataset_path}/{resource}"`; login URL is `f"{base_url}/api/auth/login"` (flat, not dataset-scoped). `get_timeline()` does `GET .../timeline`, raises `SchoolTLError` on any non-2xx, else returns `response.json()["items"]`. `create_item(item)` does `POST .../timeline/items` with `json=item`; on a `401` response, call `_login()` once (`POST` the login URL with `json={"password": admin_password}`) and retry the same `POST` once; any response still `>= 400` after that raises `SchoolTLError(response.status_code, response.json().get("error", response.text))`; otherwise returns `response.json()`. Rely on the `httpx.AsyncClient`'s own cookie jar to carry the session cookie between calls — don't track it manually.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_school_tl_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bot/school_tl_client.py tests/test_school_tl_client.py
git commit -m "feat: add School-TL API client with login-and-retry on 401"
```

---

### Task 3: Claude message classification

**Files:**
- Create: `bot/claude_assistant.py` (classification part)
- Test: `tests/test_claude_assistant.py` (classification part)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `ClassificationResult` (dataclass: `kind: Literal["query", "propose_new_item", "decline_edit"]`, `item: dict | None = None`); `async def classify_message(client: anthropic.AsyncAnthropic, model: str, message: str, today: date) -> ClassificationResult`. Also module-level constants `QUERY_TIMELINE_TOOL`, `PROPOSE_NEW_ITEM_TOOL`, `DECLINE_EDIT_TOOL` (each a `dict` — the Anthropic tool-schema shape), used again by Task 4's module.

**Tool schemas** (exact — these are what the implementer writes verbatim):

```python
QUERY_TIMELINE_TOOL = {
    "name": "query_timeline",
    "description": (
        "Use when the user is asking a question about what's on the class "
        "timeline (dates, upcoming items, whether something specific is "
        "happening) rather than asking to add or change anything."
    ),
    "input_schema": {"type": "object", "properties": {}},
}

PROPOSE_NEW_ITEM_TOOL = {
    "name": "propose_new_item",
    "description": "Use when the user wants to add a brand-new item to the class timeline.",
    "input_schema": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["holiday", "test", "notice", "project"]},
            "m": {"type": "integer", "minimum": 1, "maximum": 12},
            "y": {"type": "integer"},
            "title": {"type": "string"},
            "short": {
                "type": "string",
                "description": "Short Hebrew summary. Must include the item's exact date within the month, resolved from the message and today's date.",
            },
            "full": {"type": "string", "description": "Longer Hebrew description."},
            "required-white-shirt": {"type": "boolean"},
            "required-food": {"type": "boolean"},
            "required-parent-signature": {"type": "boolean"},
        },
        "required": ["type", "m", "y", "title", "short", "full"],
    },
}

DECLINE_EDIT_TOOL = {
    "name": "decline_edit_request",
    "description": "Use when the user is asking to edit, change, move, or delete an existing timeline item — not supported yet.",
    "input_schema": {"type": "object", "properties": {}},
}
```

- [ ] **Step 1: Write the failing tests**

Mock `client.messages.create` (an `unittest.mock.AsyncMock`) to return a `types.SimpleNamespace(content=[...])` shaped like the real SDK response.

```python
@pytest.mark.asyncio
async def test_classify_message_returns_query_for_a_question():
    client = make_fake_client(tool_name="query_timeline", tool_input={})
    result = await classify_message(client, "claude-sonnet-5-5", "מה יש השבוע?", date(2026, 11, 8))
    assert result == ClassificationResult(kind="query")

@pytest.mark.asyncio
async def test_classify_message_returns_propose_new_item_with_extracted_fields():
    extracted = {"type": "test", "m": 11, "y": 2026, "title": "מבחן במתמטיקה",
                 "short": "מבחן במתמטיקה - יום שני, 16.11", "full": "מבחן במתמטיקה, חומר: פרקים 1-3"}
    client = make_fake_client(tool_name="propose_new_item", tool_input=extracted)
    result = await classify_message(client, "claude-sonnet-5-5", "תוסיף מבחן במתמטיקה ביום שני הקרוב", date(2026, 11, 8))
    assert result == ClassificationResult(kind="propose_new_item", item=extracted)

@pytest.mark.asyncio
async def test_classify_message_returns_decline_edit_for_an_edit_request():
    client = make_fake_client(tool_name="decline_edit_request", tool_input={})
    result = await classify_message(client, "claude-sonnet-5-5", "תזיז את המבחן לדצמבר", date(2026, 11, 8))
    assert result == ClassificationResult(kind="decline_edit")
```

Define `make_fake_client(tool_name, tool_input)` at module scope: builds a `Mock()` whose `.messages.create` is an `AsyncMock(return_value=types.SimpleNamespace(content=[types.SimpleNamespace(type="tool_use", name=tool_name, input=tool_input)]))`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_claude_assistant.py -v -k classify`
Expected: FAIL with `ModuleNotFoundError` for `bot.claude_assistant`.

- [ ] **Step 3: Implement `ClassificationResult` and `classify_message` in `bot/claude_assistant.py`**

Call `client.messages.create(model=model, max_tokens=1024, system=<system prompt stating today's date and that the assistant must always call exactly one of the three tools>, messages=[{"role": "user", "content": message}], tools=[QUERY_TIMELINE_TOOL, PROPOSE_NEW_ITEM_TOOL, DECLINE_EDIT_TOOL], tool_choice={"type": "any"})`. Find the first block in `response.content` where `block.type == "tool_use"`. Map `block.name == "query_timeline"` → `ClassificationResult(kind="query")`; `"propose_new_item"` → `ClassificationResult(kind="propose_new_item", item=block.input)`; `"decline_edit_request"` → `ClassificationResult(kind="decline_edit")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_claude_assistant.py -v -k classify`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bot/claude_assistant.py tests/test_claude_assistant.py
git commit -m "feat: classify incoming Hebrew messages via Claude tool-use"
```

---

### Task 4: Claude query answering

**Files:**
- Modify: `bot/claude_assistant.py` (add to the file from Task 3)
- Modify: `tests/test_claude_assistant.py` (add to the file from Task 3)

**Interfaces:**
- Consumes: nothing new from earlier tasks (uses the same `anthropic.AsyncAnthropic` client type as Task 3).
- Produces: `async def answer_query(client: anthropic.AsyncAnthropic, model: str, question: str, items: list[dict], today: date) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_answer_query_returns_claude_text_response():
    client = make_fake_text_client("יש מבחן במתמטיקה ביום שני.")
    answer = await answer_query(client, "claude-sonnet-5-5", "מה יש השבוע?",
                                 [{"title": "מבחן במתמטיקה", "short": "יום שני, 16.11"}], date(2026, 11, 8))
    assert answer == "יש מבחן במתמטיקה ביום שני."

@pytest.mark.asyncio
async def test_answer_query_handles_empty_timeline():
    client = make_fake_text_client("אין כרגע פריטים בציר הזמן.")
    answer = await answer_query(client, "claude-sonnet-5-5", "מה יש השבוע?", [], date(2026, 11, 8))
    assert answer == "אין כרגע פריטים בציר הזמן."
    call_kwargs = client.messages.create.call_args.kwargs
    assert "[]" in call_kwargs["messages"][0]["content"]  # empty list was actually passed through, not skipped
```

Define `make_fake_text_client(text)` at module scope: `Mock()` whose `.messages.create` is an `AsyncMock(return_value=types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)]))`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_claude_assistant.py -v -k answer_query`
Expected: FAIL with `AttributeError`/`ImportError` for `answer_query`.

- [ ] **Step 3: Implement `answer_query` in `bot/claude_assistant.py`**

Call `client.messages.create(model=model, max_tokens=1024, system=<system prompt stating today's date and instructing the assistant to answer in Hebrew using only the given items, including exact dates read out of each item's short/full text, and to say plainly when nothing matches>, messages=[{"role": "user", "content": f"<question>\n\nItems (JSON): {json.dumps(items, ensure_ascii=False)}"}])` — no `tools` argument. Return `response.content[0].text`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_claude_assistant.py -v -k answer_query`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bot/claude_assistant.py tests/test_claude_assistant.py
git commit -m "feat: compose Hebrew answers to timeline questions via Claude"
```

---

### Task 5: Item summary formatting and pending-proposal store

**Files:**
- Create: `bot/formatting.py`
- Create: `bot/pending.py`
- Test: `tests/test_formatting.py`
- Test: `tests/test_pending.py`

**Interfaces:**
- Produces: `def format_item_summary(item: dict) -> str` (in `bot/formatting.py`); `PendingProposals` (in `bot/pending.py`) with `def set(self, chat_id: int, item: dict) -> None`, `def pop(self, chat_id: int) -> dict | None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_format_item_summary_includes_every_field_the_user_should_check():
    item = {"type": "test", "m": 11, "y": 2026, "title": "מבחן במתמטיקה",
             "short": "יום שני, 16.11", "full": "חומר: פרקים 1-3",
             "required-white-shirt": False, "required-food": False, "required-parent-signature": False}
    text = format_item_summary(item)
    for value in ["מבחן במתמטיקה", "יום שני, 16.11", "חומר: פרקים 1-3"]:
        assert value in text

def test_format_item_summary_flags_required_white_shirt():
    item = {**BASE_ITEM, "required-white-shirt": True}
    assert "חולצה לבנה" in format_item_summary(item)
```

```python
def test_pending_proposals_set_then_pop_returns_the_item():
    store = PendingProposals()
    store.set(123, {"title": "a"})
    assert store.pop(123) == {"title": "a"}

def test_pending_proposals_pop_twice_returns_none_the_second_time():
    store = PendingProposals()
    store.set(123, {"title": "a"})
    store.pop(123)
    assert store.pop(123) is None

def test_pending_proposals_set_again_replaces_the_earlier_pending_item():
    store = PendingProposals()
    store.set(123, {"title": "first"})
    store.set(123, {"title": "second"})
    assert store.pop(123) == {"title": "second"}
```

Define `BASE_ITEM` in `tests/test_formatting.py` with the same shape as the item above, `"required-white-shirt": False` etc., reused across formatting tests.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_formatting.py tests/test_pending.py -v`
Expected: FAIL with `ModuleNotFoundError` for `bot.formatting` / `bot.pending`.

- [ ] **Step 3: Implement `format_item_summary` in `bot/formatting.py` and `PendingProposals` in `bot/pending.py`**

`format_item_summary` renders a multi-line Hebrew string with the title, the `short` date text, the `full` description, and a line per `True` boolean flag (`required-white-shirt` → mentions "חולצה לבנה", `required-food` → "אוכל", `required-parent-signature` → "חתימת הורה") — omit a flag's line entirely when it's `False`. `PendingProposals` wraps a plain `dict[int, dict]`; `set` overwrites any existing entry for that `chat_id`; `pop` is `dict.pop(chat_id, None)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_formatting.py tests/test_pending.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bot/formatting.py bot/pending.py tests/test_formatting.py tests/test_pending.py
git commit -m "feat: add Hebrew item-summary formatting and pending-proposal store"
```

---

### Task 6: Telegram handlers

**Files:**
- Create: `bot/telegram_bot.py`
- Test: `tests/test_telegram_bot.py`

**Interfaces:**
- Consumes: `Config` (Task 1); `SchoolTLClient`, `SchoolTLError` (Task 2); `ClassificationResult`, `classify_message`, `answer_query` (Task 3, 4); `format_item_summary` (Task 5); `PendingProposals` (Task 5).
- Produces: `def build_application(config: Config, school_tl_client: SchoolTLClient, claude_client: anthropic.AsyncAnthropic, pending: PendingProposals) -> telegram.ext.Application`; internally registered handlers `handle_text_message` and `handle_confirmation_callback` (not required to be imported elsewhere, but must be unit-testable — define them as free functions in this module, not inline closures, so the tests below can call them directly).

**Handler behavior to implement (drives the steps below):**
- `handle_text_message(update, context)`: if `update.effective_user.id` isn't in `context.bot_data["config"].allowed_user_ids`, reply "אין לך הרשאה להשתמש בבוט הזה." and return. Otherwise call `classify_message`. On `kind == "query"`: fetch `get_timeline()`, call `answer_query`, reply with the result. On `kind == "propose_new_item"`: `pending.set(update.effective_chat.id, result.item)`, reply with `format_item_summary(result.item)` plus an inline keyboard (`callback_data="confirm"` / `"cancel"`). On `kind == "decline_edit"`: reply with a fixed Hebrew message stating editing existing items isn't supported yet.
- `handle_confirmation_callback(update, context)`: on `update.callback_query.data == "confirm"`, `item = pending.pop(chat_id)`; if `None`, edit the message to say there's nothing pending; else call `create_item(item)` — on success edit the message to a Hebrew success line naming the created item's `id`; on `SchoolTLError`, edit the message with a Hebrew failure line including `error.message`. On `"cancel"`, `pending.pop(chat_id)` and edit the message to a Hebrew "cancelled" line regardless of whether anything was actually pending.

- [ ] **Step 1: Write the failing tests**

Build minimal fake `Update`/`Context` objects with `unittest.mock` rather than real `telegram` objects — only the attributes/methods the handlers touch are needed: `update.effective_user.id`, `update.effective_chat.id`, `update.message.reply_text` (`AsyncMock`), `update.callback_query.data`, `update.callback_query.edit_message_text` (`AsyncMock`), `context.bot_data`.

```python
@pytest.mark.asyncio
async def test_handle_text_message_rejects_unauthorized_user():
    update, context = make_update_and_context(user_id=999, config=make_config(allowed_user_ids={111}))
    await handle_text_message(update, context)
    update.message.reply_text.assert_awaited_once()
    assert "הרשאה" in update.message.reply_text.call_args.args[0]
    context.bot_data["claude_client"].messages.create.assert_not_called()

@pytest.mark.asyncio
async def test_handle_text_message_replies_with_query_answer():
    update, context = make_update_and_context(user_id=111, classify_result=ClassificationResult(kind="query"))
    context.bot_data["school_tl_client"].get_timeline = AsyncMock(return_value=[])
    context.bot_data["answer_query"] = AsyncMock(return_value="אין פריטים.")
    await handle_text_message(update, context)
    update.message.reply_text.assert_awaited_once_with("אין פריטים.")

@pytest.mark.asyncio
async def test_handle_text_message_stores_pending_and_shows_confirmation_for_new_item():
    item = {"title": "מבחן", "short": "16.11", "full": "x", "type": "test", "m": 11, "y": 2026}
    update, context = make_update_and_context(user_id=111, classify_result=ClassificationResult(kind="propose_new_item", item=item))
    await handle_text_message(update, context)
    assert context.bot_data["pending"].pop(update.effective_chat.id) == item
    update.message.reply_text.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_text_message_declines_edit_requests():
    update, context = make_update_and_context(user_id=111, classify_result=ClassificationResult(kind="decline_edit"))
    await handle_text_message(update, context)
    update.message.reply_text.assert_awaited_once()
    context.bot_data["school_tl_client"].create_item.assert_not_called()

@pytest.mark.asyncio
async def test_handle_text_message_second_proposal_replaces_first():
    pending = PendingProposals()
    pending.set(42, {"title": "first"})
    update, context = make_update_and_context(
        user_id=111, chat_id=42, pending=pending,
        classify_result=ClassificationResult(kind="propose_new_item", item={"title": "second"}))
    await handle_text_message(update, context)
    assert pending.pop(42) == {"title": "second"}

@pytest.mark.asyncio
async def test_handle_confirmation_callback_confirm_creates_item_and_reports_success():
    pending = PendingProposals()
    pending.set(42, {"title": "מבחן"})
    update, context = make_update_and_context(chat_id=42, pending=pending, callback_data="confirm")
    context.bot_data["school_tl_client"].create_item = AsyncMock(return_value={"id": "new-1", "title": "מבחן"})
    await handle_confirmation_callback(update, context)
    context.bot_data["school_tl_client"].create_item.assert_awaited_once_with({"title": "מבחן"})
    update.callback_query.edit_message_text.assert_awaited_once()
    assert "new-1" in update.callback_query.edit_message_text.call_args.args[0]

@pytest.mark.asyncio
async def test_handle_confirmation_callback_confirm_reports_school_tl_error():
    pending = PendingProposals()
    pending.set(42, {"title": "מבחן"})
    update, context = make_update_and_context(chat_id=42, pending=pending, callback_data="confirm")
    context.bot_data["school_tl_client"].create_item = AsyncMock(side_effect=SchoolTLError(400, "title is required"))
    await handle_confirmation_callback(update, context)
    assert "title is required" in update.callback_query.edit_message_text.call_args.args[0]

@pytest.mark.asyncio
async def test_handle_confirmation_callback_cancel_discards_pending_without_writing():
    pending = PendingProposals()
    pending.set(42, {"title": "מבחן"})
    update, context = make_update_and_context(chat_id=42, pending=pending, callback_data="cancel")
    await handle_confirmation_callback(update, context)
    context.bot_data["school_tl_client"].create_item.assert_not_called()
    assert pending.pop(42) is None
```

Define `make_config(allowed_user_ids={111})` at module scope: returns a `Config` with that `allowed_user_ids` and arbitrary fixed placeholder strings for every other required field (e.g. `"x"`), used wherever a test needs a `Config` without caring about its other fields. Define a single `make_update_and_context(...)` helper at module scope covering all the fixtures above (`user_id`, `chat_id=1` default, `config=make_config()` default, overridable, `classify_result` patched in as `context.bot_data["classify_message"]`'s return value via `AsyncMock`, `pending` defaulting to a fresh `PendingProposals()`, `callback_data=None`). Populate `context.bot_data` with: real `config` and `pending` instances; `school_tl_client = Mock(get_timeline=AsyncMock(return_value=[]), create_item=AsyncMock(return_value={"id": "stub"}))` (a plain `Mock()` with those two attributes explicitly set to `AsyncMock`, not an autospec); `claude_client = Mock()` (present but never actually called in these tests, since `classify_message`/`answer_query` are swapped below); `classify_message = AsyncMock(return_value=classify_result)`; `answer_query = AsyncMock(return_value="")`. Each test overrides only the entries it cares about.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_telegram_bot.py -v`
Expected: FAIL with `ModuleNotFoundError` for `bot.telegram_bot`.

- [ ] **Step 3: Implement `handle_text_message`, `handle_confirmation_callback`, and `build_application` in `bot/telegram_bot.py`**

Read all collaborators (`config`, `school_tl_client`, `claude_client`, `pending`, `classify_message`, `answer_query`) from `context.bot_data`, exactly as the test helper populates it — this is what lets the tests inject fakes without patching imports. `build_application(config, school_tl_client, claude_client, pending)` constructs a `telegram.ext.Application`, and sets `application.bot_data` to a dict with: the four parameters under `"config"`, `"school_tl_client"`, `"claude_client"`, `"pending"`; and, under `"classify_message"`/`"answer_query"`, the real `classify_message`/`answer_query` functions imported directly from `bot.claude_assistant` (they're stateless, so they're wired in here rather than taken as constructor parameters). It then registers a `MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)` and a `CallbackQueryHandler(handle_confirmation_callback)`, and returns the application (does not call `run_polling()` — that's Task 7).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_telegram_bot.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bot/telegram_bot.py tests/test_telegram_bot.py
git commit -m "feat: add Telegram message and confirmation-callback handlers"
```

---

### Task 7: Entrypoint and project files

**Files:**
- Create: `bot/main.py`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.env.example`
- Modify: `.gitignore` (add `.env` — the real file holding live secrets must never be committed; only `.env.example` is tracked)
- Modify: `CLAUDE.md` (fill in the "when real application code lands" section from the main-branch `CLAUDE.md`, per its own instruction, with these commands)

**Interfaces:**
- Consumes: `load_config` (Task 1), `SchoolTLClient` (Task 2), `build_application` (Task 6).
- Produces: nothing consumed by another task — this is the last one.

- [ ] **Step 1: Write `requirements.txt`**

```
python-telegram-bot>=21,<22
httpx>=0.27,<1
anthropic>=0.40,<1
```

- [ ] **Step 2: Write `requirements-dev.txt`**

```
-r requirements.txt
pytest>=8,<9
pytest-asyncio>=0.24,<1
respx>=0.21,<1
```

- [ ] **Step 3: Write `.env.example`**

```
TELEGRAM_BOT_TOKEN=
ANTHROPIC_API_KEY=
CLAUDE_MODEL=claude-sonnet-5-5
SCHOOL_TL_BASE_URL=https://reutl.vercel.app
SCHOOL_TL_SCHOOL=reut
SCHOOL_TL_PERIOD=2026-2027
SCHOOL_TL_CLASS=e4
SCHOOL_TL_ADMIN_PASSWORD=
ALLOWED_TELEGRAM_USER_IDS=
```

- [ ] **Step 4: Add `.env` to `.gitignore`**

Append a line `.env` to the existing `.gitignore` (keep its current three entries unchanged).

- [ ] **Step 5: Implement `bot/main.py`**

`def main() -> None`: `config = load_config(os.environ)`; build one shared `httpx.AsyncClient()` and one `anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)`; build a `SchoolTLClient` from `config`'s relevant fields and that `httpx.AsyncClient`; build a `PendingProposals()`; call `build_application(config, school_tl_client, claude_client, pending)`; call `application.run_polling()`. Guard with `if __name__ == "__main__": main()`.

- [ ] **Step 6: Install dependencies and run the full test suite**

Run: `pip install -r requirements-dev.txt && pytest -v`
Expected: all tests from Tasks 1-6 PASS.

- [ ] **Step 7: Manual smoke test against a disposable School-TL dataset**

Per the spec's "Testing against real data": set `SCHOOL_TL_SCHOOL=_test`, `SCHOOL_TL_PERIOD=0000`, `SCHOOL_TL_CLASS=zz` (or similar) in a local `.env`, run `python -m bot.main`, and from Telegram: ask a question against the (empty) disposable dataset, then propose a new item and confirm it, and verify in the bot's replies that the create actually succeeded (a real `id` comes back). Do not point this manual test at `reut/2026-2027/e4` — that's a separate, deliberate step the user runs themselves once satisfied.

- [ ] **Step 8: Commit**

```bash
git add bot/main.py requirements.txt requirements-dev.txt .env.example .gitignore CLAUDE.md
git commit -m "feat: add bot entrypoint and project/run files"
```

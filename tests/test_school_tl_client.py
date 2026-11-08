import json

import httpx
import pytest
import respx

from bot.school_tl_client import SchoolTLClient, SchoolTLError


def make_client(admin_password="secret"):
    http_client = httpx.AsyncClient(base_url="https://fake.example")
    return SchoolTLClient(
        http_client,
        base_url="https://fake.example",
        school="reut",
        period="2026-2027",
        school_class="e4",
        admin_password=admin_password,
    )


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
        side_effect=[
            httpx.Response(401, json={"error": "Authentication required"}),
            httpx.Response(201, json={"id": "new-1", "title": "מבחן"}),
        ]
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
        side_effect=[
            httpx.Response(401, json={"error": "Authentication required"}),
            httpx.Response(201, json={"id": "1"}),
        ]
    )
    client = make_client(admin_password="correct-secret")
    await client.create_item({"title": "x"})
    sent_body = json.loads(route.calls[0].request.content)
    assert sent_body == {"password": "correct-secret"}

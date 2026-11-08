import json
from dataclasses import dataclass
from datetime import date
from typing import Literal

import anthropic

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


@dataclass
class ClassificationResult:
    kind: Literal["query", "propose_new_item", "decline_edit"]
    item: dict | None = None


def _classification_system_prompt(today: date) -> str:
    return (
        f"Today's date is {today.isoformat()}. You are classifying a Hebrew message "
        "sent to a school-class-timeline bot. You must always call exactly one of the "
        "three provided tools: query_timeline for a question about the timeline, "
        "propose_new_item to add a brand-new item (resolving any relative dates like "
        "'next Monday' against today's date), or decline_edit_request if the message "
        "asks to edit, move, or delete an existing item."
    )


async def classify_message(
    client: anthropic.AsyncAnthropic, model: str, message: str, today: date
) -> ClassificationResult:
    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=_classification_system_prompt(today),
        messages=[{"role": "user", "content": message}],
        tools=[QUERY_TIMELINE_TOOL, PROPOSE_NEW_ITEM_TOOL, DECLINE_EDIT_TOOL],
        tool_choice={"type": "any"},
    )
    tool_use = next(block for block in response.content if block.type == "tool_use")
    if tool_use.name == "query_timeline":
        return ClassificationResult(kind="query")
    if tool_use.name == "propose_new_item":
        return ClassificationResult(kind="propose_new_item", item=tool_use.input)
    return ClassificationResult(kind="decline_edit")


def _answer_system_prompt(today: date) -> str:
    return (
        f"Today's date is {today.isoformat()}. Answer the user's Hebrew question about "
        "their school class timeline, in Hebrew, using only the given items. Read exact "
        "dates out of each item's short/full text where the question needs one. If "
        "nothing in the items matches the question, say so plainly rather than guessing."
    )


async def answer_query(
    client: anthropic.AsyncAnthropic,
    model: str,
    question: str,
    items: list[dict],
    today: date,
) -> str:
    items_json = json.dumps(items, ensure_ascii=False)
    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=_answer_system_prompt(today),
        messages=[{"role": "user", "content": f"{question}\n\nItems (JSON): {items_json}"}],
    )
    return response.content[0].text

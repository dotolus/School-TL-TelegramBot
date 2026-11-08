_FLAG_LABELS = {
    "required-white-shirt": "חולצה לבנה",
    "required-food": "אוכל",
    "required-parent-signature": "חתימת הורה",
}


def format_item_summary(item: dict) -> str:
    lines = [item["title"], item["short"], item["full"]]
    for flag, label in _FLAG_LABELS.items():
        if item.get(flag):
            lines.append(f"דרוש: {label}")
    return "\n".join(lines)

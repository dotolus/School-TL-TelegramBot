_FLAG_LABELS = {
    "required-white-shirt": "חולצה לבנה",
    "required-food": "אוכל",
    "required-parent-signature": "חתימת הורה",
}

_TYPE_LABELS = {
    "holiday": "חג",
    "test": "מבחן",
    "notice": "הודעה",
    "project": "פרויקט",
}


def format_item_summary(item: dict) -> str:
    type_label = _TYPE_LABELS.get(item["type"], item["type"])
    lines = [
        item["title"],
        f"סוג: {type_label} | תאריך: {item['m']}/{item['y']}",
        item["short"],
        item["full"],
    ]
    for flag, label in _FLAG_LABELS.items():
        if item.get(flag):
            lines.append(f"דרוש: {label}")
    return "\n".join(lines)

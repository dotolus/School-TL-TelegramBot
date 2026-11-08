from bot.formatting import format_item_summary

BASE_ITEM = {
    "type": "test",
    "m": 11,
    "y": 2026,
    "title": "מבחן במתמטיקה",
    "short": "יום שני, 16.11",
    "full": "חומר: פרקים 1-3",
    "required-white-shirt": False,
    "required-food": False,
    "required-parent-signature": False,
}


def test_format_item_summary_includes_every_field_the_user_should_check():
    text = format_item_summary(BASE_ITEM)
    for value in ["מבחן במתמטיקה", "יום שני, 16.11", "חומר: פרקים 1-3"]:
        assert value in text


def test_format_item_summary_flags_required_white_shirt():
    item = {**BASE_ITEM, "required-white-shirt": True}
    assert "חולצה לבנה" in format_item_summary(item)


def test_format_item_summary_includes_type_and_month_year():
    text = format_item_summary(BASE_ITEM)
    assert "מבחן" in text  # Hebrew label for type "test"
    assert "11/2026" in text  # m/y, so a wrong month/year is visible before confirming

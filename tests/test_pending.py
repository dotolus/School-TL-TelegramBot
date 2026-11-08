from bot.pending import PendingProposals


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

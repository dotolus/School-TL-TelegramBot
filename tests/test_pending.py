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


def test_pending_proposals_set_returns_a_token_and_peek_returns_it():
    store = PendingProposals()
    token = store.set(123, {"title": "a"})
    assert store.peek_token(123) == token


def test_pending_proposals_peek_token_is_none_when_nothing_pending():
    store = PendingProposals()
    assert store.peek_token(123) is None


def test_pending_proposals_pop_with_stale_token_returns_none_and_keeps_the_newer_item():
    store = PendingProposals()
    stale_token = store.set(123, {"title": "first"})
    store.set(123, {"title": "second"})
    assert store.pop(123, stale_token) is None
    assert store.peek_token(123) is not None  # the newer item is still pending


def test_pending_proposals_pop_with_matching_token_removes_it():
    store = PendingProposals()
    token = store.set(123, {"title": "a"})
    assert store.pop(123, token) == {"title": "a"}
    assert store.peek_token(123) is None


def test_pending_proposals_pop_without_a_token_ignores_token_matching():
    store = PendingProposals()
    store.set(123, {"title": "a"})
    assert store.pop(123) == {"title": "a"}

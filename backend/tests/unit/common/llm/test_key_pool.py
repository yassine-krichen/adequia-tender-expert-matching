from app.common.llm.key_pool import KeyPool, parse_key_pool


def test_parse_key_pool_splits_and_strips_comma_separated_keys() -> None:
    assert parse_key_pool(" key-1, key-2 ,key-3") == ["key-1", "key-2", "key-3"]


def test_parse_key_pool_returns_empty_list_for_blank_string() -> None:
    assert parse_key_pool("") == []


def test_next_available_key_rotates_round_robin() -> None:
    pool = KeyPool("groq", ["k1", "k2", "k3"])

    assert [pool.next_available_key() for _ in range(4)] == ["k1", "k2", "k3", "k1"]


def test_next_available_key_skips_rate_limited_keys() -> None:
    pool = KeyPool("groq", ["k1", "k2"])

    pool.mark_rate_limited("k1")

    assert pool.next_available_key() == "k2"
    assert pool.next_available_key() == "k2"


def test_next_available_key_returns_none_when_every_key_is_cooling_down() -> None:
    pool = KeyPool("groq", ["k1", "k2"])

    pool.mark_rate_limited("k1")
    pool.mark_rate_limited("k2")

    assert pool.next_available_key() is None


def test_next_available_key_returns_none_for_empty_pool() -> None:
    pool = KeyPool("groq", [])

    assert pool.next_available_key() is None

from store.fts_safe import fts_safe_terms


def test_fts_safe_strips_operators() -> None:
    assert fts_safe_terms('foo OR bar') == '"foo" AND "bar"'
    assert fts_safe_terms("*") == ""
    assert fts_safe_terms("hello world") == '"hello" AND "world"'


def test_fts_safe_empty_on_noise() -> None:
    assert fts_safe_terms("!!!") == ""


def test_fts_safe_neutralizes_match_operators() -> None:
    q = fts_safe_terms('foo" OR bar NEAR baz NOT qux')
    parts = q.split(" AND ")
    assert parts
    assert all(p.startswith('"') and p.endswith('"') for p in parts)
    assert " NEAR " not in q
    assert " OR " not in q

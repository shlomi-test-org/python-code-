import pytest

from src.lib.data.mongo.index_matchers import IndexMatcher


@pytest.mark.parametrize("index_fields, filters, expected", [
    (("a", "b", "c"), {}, False),
    (["a", "b", "c"], {"a": 1}, True),
    (["a", "b", "c"], {"a": 1, "b": 2}, True),
    (("a", "b", "c"), {"a": 1, "c": 3}, False),
    (["a", "b", "c"], {"d": 4}, False),
    (["a", "b", "c"], {"a": 1, "b": 2, "c": 3, "d": 4}, False)
])
def test_index_matcher_parametrized(index_fields, filters, expected):
    matcher = IndexMatcher(index_fields)
    assert matcher.match(filters) == expected

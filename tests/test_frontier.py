import pytest

from crawler.frontier import Frontier, Task


def test_bfs_order():
    f = Frontier("bfs")
    for name in "abc":
        f.push(Task(name))
    assert [f.pop().url for _ in range(3)] == ["a", "b", "c"]


def test_dfs_order():
    f = Frontier("dfs")
    for name in "abc":
        f.push(Task(name))
    assert [f.pop().url for _ in range(3)] == ["c", "b", "a"]


def test_best_order():
    f = Frontier("best")
    f.push(Task("low", priority=1))
    f.push(Task("high", priority=9))
    f.push(Task("mid", priority=5))
    assert [f.pop().url for _ in range(3)] == ["high", "mid", "low"]


def test_best_same_priority_is_fifo():
    f = Frontier("best")
    f.push(Task("first", priority=1))
    f.push(Task("second", priority=1))
    assert [f.pop().url, f.pop().url] == ["first", "second"]


def test_duplicate_url_not_pushed():
    f = Frontier("bfs")
    assert f.push(Task("http://a.com/x")) is True
    assert f.push(Task("http://a.com/x")) is False
    assert f.dup == 1
    assert len(f) == 1


def test_pop_empty_returns_none():
    for strategy in Frontier.STRATEGIES:
        assert Frontier(strategy).pop() is None


def test_unknown_strategy():
    with pytest.raises(ValueError):
        Frontier("random")

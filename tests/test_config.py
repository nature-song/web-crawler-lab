import pytest

from crawler.config import CrawlConfig


def test_validate_ok():
    assert CrawlConfig(seeds=["http://a.com/"]).validate() == (True, "")


def test_validate_empty_seeds():
    ok, msg = CrawlConfig().validate()
    assert not ok
    assert "种子" in msg


@pytest.mark.parametrize(
    "field_name, value",
    [
        ("strategy", "random"),
        ("max_depth", 11),
        ("max_pages", 0),
        ("interval", 0),
        ("workers", 9),
        ("timeout", 0),
        ("retries", 6),
    ],
)
def test_validate_rejects_out_of_range(field_name, value):
    cfg = CrawlConfig(seeds=["http://a.com/"])
    setattr(cfg, field_name, value)
    assert cfg.validate()[0] is False

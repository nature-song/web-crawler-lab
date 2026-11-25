import pytest

from crawler.config import CrawlConfig
from crawler.url_utils import host_of, is_pdf, normalize_url, should_visit


@pytest.mark.parametrize(
    "raw, base, want",
    [
        ("HTTP://Example.COM:80/a/../b/?utm_source=x&b=2&a=1#top", None, "http://example.com/b?a=1&b=2"),
        ("/x#top", "http://127.0.0.1:8000/", "http://127.0.0.1:8000/x"),
        ("../news/p1.html", "http://127.0.0.1:8000/a/b/index.html", "http://127.0.0.1:8000/a/news/p1.html"),
        ("https://A.com:443/x/", None, "https://a.com/x"),
        ("http://a.com//x///y", None, "http://a.com/x/y"),
        ("http://a.com", None, "http://a.com/"),
    ],
)
def test_normalize(raw, base, want):
    assert normalize_url(raw, base) == want


@pytest.mark.parametrize(
    "raw", ["javascript:void(0)", "mailto:a@b.com", "#", "ftp://a.com/x", ""]
)
def test_normalize_rejects(raw):
    assert normalize_url(raw) is None


def test_should_visit_depth():
    cfg = CrawlConfig(seeds=["http://a.com/"], max_depth=2)
    assert should_visit("http://a.com/p", 2, cfg, "a.com") == (True, "")
    assert should_visit("http://a.com/p", 3, cfg, "a.com") == (False, "depth")


def test_should_visit_suffix():
    cfg = CrawlConfig(seeds=["http://a.com/"])
    assert should_visit("http://a.com/a.jpg", 0, cfg, "a.com") == (False, "suffix")
    assert should_visit("http://a.com/a.pdf", 0, cfg, "a.com") == (True, "")


def test_should_visit_offsite():
    cfg = CrawlConfig(seeds=["http://a.com/"])
    assert should_visit("http://b.com/x", 0, cfg, "a.com") == (False, "offsite")
    cfg.same_domain = False
    assert should_visit("http://b.com/x", 0, cfg, "a.com") == (True, "")


def test_host_of():
    assert host_of("http://A.com:8080/x") == "a.com"


def test_is_pdf():
    assert is_pdf("http://a.com/f.PDF?x=1") is True
    assert is_pdf("http://a.com/f.html") is False

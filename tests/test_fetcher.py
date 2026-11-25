import pytest
import requests

import crawler.fetcher as fetcher_module
from crawler.config import CrawlConfig
from crawler.fetcher import Fetcher, decode


class FakeResponse:
    """够用的假响应：只要 iter_content / headers / status_code / encoding。"""

    def __init__(self, status=200, headers=None, body=b"", encoding="utf-8"):
        self.status_code = status
        self.headers = headers or {}
        self.encoding = encoding
        self._body = body
        self.closed = False

    def iter_content(self, size):
        for i in range(0, len(self._body), size):
            yield self._body[i : i + size]

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.headers = {}

    def get(self, url, **kwargs):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """重试的退避不要真的睡，否则测试要跑好几秒。"""
    monkeypatch.setattr(fetcher_module.time, "sleep", lambda seconds: None)


def make_fetcher(responses, **cfg_kwargs):
    cfg = CrawlConfig(seeds=["http://a.com/"], **cfg_kwargs)
    session = FakeSession(responses)
    return Fetcher(cfg, session=session), session


def test_html_ok():
    body = "<html><title>新闻</title></html>".encode()
    resp = FakeResponse(headers={"Content-Type": "text/html; charset=utf-8"}, body=body)
    fetcher, session = make_fetcher([resp])
    result = fetcher.fetch("http://a.com/x")
    assert result.kind == "html"
    assert "新闻" in result.html
    assert session.calls == 1


def test_gbk_page_without_charset():
    body = "<html><title>中文标题</title></html>".encode("gbk")
    # 响应头没写 charset 时 requests 会填 ISO-8859-1，这种"假编码"要被忽略
    resp = FakeResponse(headers={"Content-Type": "text/html"}, body=body, encoding="ISO-8859-1")
    fetcher, _ = make_fetcher([resp])
    assert "中文标题" in fetcher.fetch("http://a.com/gbk").html


def test_pdf_by_content_type():
    resp = FakeResponse(headers={"Content-Type": "application/pdf"}, body=b"%PDF-1.4")
    fetcher, _ = make_fetcher([resp])
    assert fetcher.fetch("http://a.com/a").kind == "pdf"


def test_pdf_by_suffix():
    resp = FakeResponse(headers={"Content-Type": "application/octet-stream"}, body=b"")
    fetcher, _ = make_fetcher([resp])
    assert fetcher.fetch("http://a.com/paper.PDF").kind == "pdf"


def test_other_type():
    resp = FakeResponse(headers={"Content-Type": "application/json"}, body=b"{}")
    fetcher, _ = make_fetcher([resp])
    assert fetcher.fetch("http://a.com/api").kind == "other"


def test_404_is_not_retried():
    fetcher, session = make_fetcher([FakeResponse(status=404)])
    result = fetcher.fetch("http://a.com/x")
    assert result.kind == "error"
    assert session.calls == 1


def test_retry_then_success():
    responses = [
        requests.Timeout("超时1"),
        requests.Timeout("超时2"),
        FakeResponse(headers={"Content-Type": "text/html"}, body=b"<html>ok</html>"),
    ]
    fetcher, session = make_fetcher(responses, retries=3)
    result = fetcher.fetch("http://a.com/x")
    assert result.kind == "html"
    assert session.calls == 3


def test_retry_exhausted():
    fetcher, session = make_fetcher([requests.Timeout("超时")] * 3, retries=3)
    result = fetcher.fetch("http://a.com/x")
    assert result.kind == "error"
    assert "Timeout" in result.error
    assert session.calls == 3


def test_too_large_page(monkeypatch):
    monkeypatch.setattr(fetcher_module, "MAX_BYTES", 10)
    resp = FakeResponse(headers={"Content-Type": "text/html"}, body=b"x" * 100)
    fetcher, _ = make_fetcher([resp])
    result = fetcher.fetch("http://a.com/big")
    assert result.kind == "other"
    assert result.error == "页面过大"


def test_decode_falls_back():
    assert decode("中文".encode("gbk")) == "中文"
    assert decode(b"hello") == "hello"
    assert decode(b"\xff\xfe") != ""

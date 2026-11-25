import csv
from pathlib import Path

import pytest

from crawler.models import Page
from crawler.storage import Storage


@pytest.fixture
def store(tmp_path):
    storage = Storage(tmp_path / "test.db")
    yield storage
    storage.close()


def make_page(url="http://a.com/1", **overrides) -> Page:
    data = {
        "url": url,
        "title": "测试标题",
        "authors": "张三",
        "abstract": "这是摘要",
        "keywords": "关键词",
        "publish_date": "2025-03-14",
        "site": "a.com",
        "content_type": "text/html",
        "http_status": 200,
        "depth": 1,
        "parent_url": "http://a.com/",
        "fetched_at": "2025-11-25 10:00:00",
        "elapsed_ms": 120,
        "ok": True,
        "error": "",
    }
    data.update(overrides)
    return Page(**data)


def test_save_and_count(store):
    assert store.save(make_page()) is True
    assert store.count() == 1


def test_duplicate_url_is_ignored(store):
    store.save(make_page())
    assert store.save(make_page()) is False
    assert store.count() == 1


def test_fields_round_trip(store):
    store.save(make_page())
    row = store.query()[0]
    assert row["title"] == "测试标题"
    assert row["authors"] == "张三"
    assert row["publish_date"] == "2025-03-14"
    assert row["site"] == "a.com"
    assert row["elapsed_ms"] == 120


def test_failed_page_keeps_ok_zero(store):
    store.save(make_page(url="http://a.com/bad", ok=False, error="解析失败"))
    assert store.query()[0]["ok"] == 0


def test_save_pdf(store):
    assert store.save_pdf("http://a.com/a.pdf", found_on="http://a.com/", anchor="论文") is True
    assert store.save_pdf("http://a.com/a.pdf") is False
    assert store.count_pdf() == 1


def test_save_many(store):
    pages = [make_page(url=f"http://a.com/{i}") for i in range(25)]
    assert store.save_many(pages) == 25
    assert store.count() == 25


def test_query_filters(store):
    store.save(make_page(url="http://a.com/1", title="毕业论文开题"))
    store.save(make_page(url="http://b.com/2", site="b.com", title="别的站点"))
    store.save(make_page(url="http://a.com/3", ok=False))

    assert len(store.query()) == 3
    assert len(store.query(site="a.com")) == 2
    assert len(store.query(ok_only=True)) == 2
    assert len(store.query(keyword="毕业论文")) == 1
    assert len(store.query(limit=1)) == 1


def test_export_csv(store, tmp_path):
    store.save(make_page())
    target = tmp_path / "out" / "result.csv"
    assert store.export_csv(target) == 1

    assert target.read_bytes()[:3] == b"\xef\xbb\xbf"      # 带 BOM，Excel 才不乱码
    with target.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["title"] == "测试标题"


def test_clear(store):
    store.save(make_page())
    store.save_pdf("http://a.com/a.pdf")
    store.clear()
    assert store.count() == 0
    assert store.count_pdf() == 0


def test_context_manager(tmp_path):
    path = Path(tmp_path) / "ctx.db"
    with Storage(path) as storage:
        storage.save(make_page())
    with Storage(path) as storage:          # 重新打开，数据还在
        assert storage.count() == 1

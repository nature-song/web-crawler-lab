"""Web 层测试：用假 service，避免测试真的去爬网。"""

import pytest

from web.server import create_app


class FakeStorage:
    def __init__(self):
        self.cleared = False

    def query(self, limit=200, site="", keyword=""):
        return [
            {
                "url": "http://a.com/1",
                "title": "测试标题",
                "authors": "张三",
                "publish_date": "2025-03-14",
                "site": "a.com",
            }
        ]

    def clear(self):
        self.cleared = True


class FakeService:
    def __init__(self):
        self.storage = FakeStorage()
        self.started_with = None
        self.stopped = False
        self.paused = False
        self.resumed = False

    def start(self, cfg):
        self.started_with = cfg
        return True, ""

    def stop(self):
        self.stopped = True

    def pause(self):
        self.paused = True

    def resume(self):
        self.resumed = True

    def snapshot(self):
        return {"fetched": 3, "queued": 7}

    def state(self):
        return "running"


@pytest.fixture
def service():
    return FakeService()


@pytest.fixture
def client(service):
    app = create_app(service)
    app.config.update(TESTING=True)
    return app.test_client()


def test_index_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "网络爬虫工作台" in resp.get_data(as_text=True)


def test_start_crawl_forwards_config(client, service):
    resp = client.post("/api/crawl/start", json={"seeds": "http://a.com/ http://b.com/",
                                                 "max_pages": 10})
    assert resp.status_code == 200
    assert service.started_with.seeds == ["http://a.com/", "http://b.com/"]
    assert service.started_with.max_pages == 10


def test_start_rejects_empty_seeds(client):
    resp = client.post("/api/crawl/start", json={"seeds": ""})
    assert resp.status_code == 400
    assert "种子" in resp.get_json()["error"]


def test_start_rejects_bad_type(client):
    resp = client.post("/api/crawl/start", json={"seeds": "http://a.com/", "max_pages": "abc"})
    assert resp.status_code == 400


def test_control_endpoints(client, service):
    assert client.post("/api/crawl/pause").status_code == 200
    assert service.paused is True
    assert client.post("/api/crawl/resume").status_code == 200
    assert service.resumed is True
    assert client.post("/api/crawl/stop").status_code == 200
    assert service.stopped is True


def test_results(client):
    resp = client.get("/api/results?limit=5")
    assert resp.status_code == 200
    assert resp.get_json()[0]["title"] == "测试标题"


def test_export_csv_has_bom(client):
    resp = client.get("/api/export.csv")
    assert resp.status_code == 200
    assert resp.data.startswith(b"\xef\xbb\xbf")
    assert "测试标题" in resp.data.decode("utf-8-sig")


def test_health(client):
    assert client.get("/api/health").get_json()["state"] == "running"


def test_clear(client, service):
    assert client.post("/api/clear").status_code == 200
    assert service.storage.cleared is True

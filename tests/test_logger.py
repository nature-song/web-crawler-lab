import queue

from crawler.logger import setup_logger


def test_writes_file_and_queue(tmp_path):
    events = queue.Queue()
    path = tmp_path / "logs" / "crawl.log"

    logger = setup_logger(path, event_queue=events, console=False)
    logger.info("测试一条日志")

    assert "测试一条日志" in path.read_text(encoding="utf-8")
    event = events.get_nowait()
    assert event["type"] == "log"
    assert event["data"]["msg"] == "测试一条日志"


def test_setup_twice_does_not_duplicate_handlers(tmp_path):
    path = tmp_path / "a.log"
    setup_logger(path, console=False)
    logger = setup_logger(path, console=False)
    assert len(logger.handlers) == 1

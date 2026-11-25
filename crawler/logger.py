"""日志配置。

一条日志同时去两个地方：
  - 文件：logs/crawl.log，事后排查用；
  - 事件队列（可选）：给界面滚动显示用。

界面那边**不直接操作控件**，只从队列里取，避免跨线程改 Tk 控件导致崩溃。
"""

import contextlib
import logging
import sys
from pathlib import Path

FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
DATEFMT = "%H:%M:%S"


class EventHandler(logging.Handler):
    """把日志记录塞进事件队列，类型固定为 "log"。"""

    def __init__(self, event_queue):
        super().__init__()
        self.event_queue = event_queue

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(Exception):   # 队列满了/关了都不该影响爬虫本身
            self.event_queue.put(
                {
                    "type": "log",
                    "data": {
                        "level": record.levelname,
                        "msg": record.getMessage(),
                        "time": self.format(record).split(" [")[0],
                    },
                }
            )


def setup_logger(
    log_path: str | Path | None = None,
    level: int = logging.INFO,
    event_queue=None,
    console: bool = True,
    name: str = "crawler",
) -> logging.Logger:
    """配置并返回 logger。重复调用是安全的，不会叠加 handler。"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    for handler in list(logger.handlers):        # 先清掉上一次的，避免日志重复打印
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(FORMAT, DATEFMT)

    if console:
        stream = logging.StreamHandler(sys.stdout)
        stream.setFormatter(formatter)
        logger.addHandler(stream)

    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if event_queue is not None:
        event_handler = EventHandler(event_queue)
        event_handler.setFormatter(formatter)
        logger.addHandler(event_handler)

    return logger

"""按域名限速。

规则：同一个域名，两次请求之间至少隔 interval 秒；不同域名互不影响。
实现要点是"锁内只做算术、锁外才 sleep"，否则一个慢域名会把其他域名一起卡住。
"""

import threading
import time


class DomainRateLimiter:
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self._next_slot: dict[str, float] = {}      # host -> 下一个可以发请求的时间点
        self._overrides: dict[str, float] = {}      # 被 429 惩罚过的域名，单独记间隔
        self._lock = threading.Lock()

    def wait(self, host: str) -> None:
        """阻塞到该域名可以发请求为止。"""
        with self._lock:
            now = time.monotonic()
            gap = self._overrides.get(host, self.interval)
            slot = max(now, self._next_slot.get(host, 0.0) + gap)
            self._next_slot[host] = slot
        delay = slot - time.monotonic()
        if delay > 0:
            time.sleep(delay)

    def slow_down(self, host: str, factor: float = 2.0, ceiling: float = 10.0) -> None:
        """被 429 打回来时调用，把这个域名的间隔调大，别影响其他站点。"""
        with self._lock:
            current = self._overrides.get(host, self.interval)
            self._overrides[host] = min(current * factor, ceiling)

    def interval_for(self, host: str) -> float:
        return self._overrides.get(host, self.interval)

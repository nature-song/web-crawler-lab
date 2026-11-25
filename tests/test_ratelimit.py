import time

from crawler.ratelimit import DomainRateLimiter


def test_same_host_waits():
    limiter = DomainRateLimiter(0.05)
    started = time.monotonic()
    for _ in range(3):
        limiter.wait("a.com")
    # 三次请求之间至少要等两个间隔
    assert time.monotonic() - started >= 0.09


def test_different_host_does_not_block():
    limiter = DomainRateLimiter(0.2)
    limiter.wait("a.com")
    started = time.monotonic()
    limiter.wait("b.com")
    assert time.monotonic() - started < 0.05


def test_slow_down_only_affects_one_host():
    limiter = DomainRateLimiter(1.0)
    limiter.slow_down("a.com")
    assert limiter.interval_for("a.com") == 2.0
    assert limiter.interval_for("b.com") == 1.0

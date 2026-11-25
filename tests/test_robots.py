from crawler.robots import RobotsCache, parse_robots

UA = "CourseCrawler/1.0 (student project)"


def make(text):
    return RobotsCache(UA, fetch_text=lambda url: text)


def test_disallow():
    robots = make("User-agent: *\nDisallow: /admin/\n")
    assert robots.allowed("http://a.com/news/1") is True
    assert robots.allowed("http://a.com/admin/x") is False


def test_longer_allow_wins():
    robots = make("User-agent: *\nDisallow: /private/\nAllow: /private/public/\n")
    assert robots.allowed("http://a.com/private/x") is False
    assert robots.allowed("http://a.com/private/public/x") is True


def test_wildcard_and_anchor():
    robots = make("User-agent: *\nDisallow: /*.pdf$\n")
    assert robots.allowed("http://a.com/a.pdf") is False
    assert robots.allowed("http://a.com/a.pdf.html") is True


def test_empty_or_missing_allows_all():
    assert make("").allowed("http://a.com/x") is True
    assert make(None).allowed("http://a.com/x") is True


def test_specific_group_beats_star():
    text = "User-agent: *\nDisallow: /\n\nUser-agent: CourseCrawler\nDisallow: /tmp/\n"
    robots = make(text)
    assert robots.allowed("http://a.com/news/1") is True
    assert robots.allowed("http://a.com/tmp/1") is False


def test_crawl_delay():
    assert make("User-agent: *\nCrawl-delay: 2\n").delay_for("http://a.com/") == 2.0
    assert make("").delay_for("http://a.com/") is None


def test_cache_fetches_once_per_host():
    calls = []

    def fetch(url):
        calls.append(url)
        return "User-agent: *\nDisallow: /admin/\n"

    robots = RobotsCache(UA, fetch_text=fetch)
    robots.allowed("http://a.com/a")
    robots.allowed("http://a.com/b")
    assert len(calls) == 1


def test_disabled_ignores_file():
    robots = RobotsCache(
        UA, enabled=False, fetch_text=lambda url: "User-agent: *\nDisallow: /\n"
    )
    assert robots.allowed("http://a.com/x") is True


def test_parse_groups():
    groups = parse_robots("User-agent: *\nDisallow: /a\n\nUser-agent: bot\nDisallow: /b\n")
    assert len(groups) == 2
    assert groups[0].rules[0].pattern == "/a"
    assert groups[1].agents == ["bot"]

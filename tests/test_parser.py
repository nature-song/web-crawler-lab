import pytest

from crawler.parser import Parser, normalize_date

FULL_PAGE = """<html><head>
<meta name="citation_title" content="基于深度学习的网络流量识别">
<meta name="citation_author" content="张三, 李四">
<meta name="citation_author" content="王五">
<meta name="citation_publication_date" content="2025/03/14">
<meta name="citation_keywords" content="流量识别; 深度学习">
<meta name="description" content="本文提出一种新的流量识别方法。">
</head><body>
<h1>备选标题</h1>
<a href="/news/1">新闻一</a>
<a href="https://b.com/x">外站</a>
<a href="#top">回到顶部</a>
<a rel="nofollow" href="/skip">别跟</a>
<a href="javascript:void(0)">假链接</a>
</body></html>"""


@pytest.fixture
def parser():
    return Parser()


def test_full_meta_page(parser):
    page, links = parser.parse(FULL_PAGE, "http://a.com/news/p1.html")
    assert page.title == "基于深度学习的网络流量识别"
    assert page.authors == "张三; 李四; 王五"
    assert page.publish_date == "2025-03-14"
    assert page.keywords == "流量识别; 深度学习"
    assert page.abstract == "本文提出一种新的流量识别方法。"
    assert page.site == "a.com"
    assert page.ok is True
    assert links == ["http://a.com/news/1", "https://b.com/x"]


def test_title_falls_back_to_h1(parser):
    page, _ = parser.parse("<html><body><h1>只有一级标题</h1></body></html>", "http://a.com/x")
    assert page.title == "只有一级标题"


def test_title_falls_back_to_title_tag(parser):
    page, _ = parser.parse("<html><head><title>网页标题</title></head></html>", "http://a.com/x")
    assert page.title == "网页标题"


def test_date_from_time_tag(parser):
    html = '<html><body><time datetime="2024-07-09T10:00:00+08:00">7月9日</time></body></html>'
    page, _ = parser.parse(html, "http://a.com/x")
    assert page.publish_date == "2024-07-09"


def test_date_from_body_text(parser):
    page, _ = parser.parse("<html><body><p>发布于 2024年7月9日</p></body></html>", "http://a.com/x")
    assert page.publish_date == "2024-07-09"


def test_invalid_date_left_empty(parser):
    html = '<html><head><meta name="citation_publication_date" content="2025/13/40"></head></html>'
    page, _ = parser.parse(html, "http://a.com/x")
    assert page.publish_date == ""


def test_abstract_falls_back_to_paragraph(parser):
    long_text = "这是一段足够长的正文内容，用来验证摘要的兜底逻辑能不能正常工作。"
    page, _ = parser.parse(f"<html><body><p>{long_text}</p></body></html>", "http://a.com/x")
    assert page.abstract == long_text


def test_max_links():
    parser = Parser(max_links=3)
    html = "<html><body>" + "".join(f'<a href="/p{i}">p</a>' for i in range(10)) + "</body></html>"
    _, links = parser.parse(html, "http://a.com/")
    assert len(links) == 3


def test_broken_html_does_not_raise(parser):
    page, links = parser.parse("<html><body><p>未闭合的标签<div><span>", "http://a.com/x")
    assert page.ok is True
    assert links == []


def test_empty_page(parser):
    page, links = parser.parse("", "http://a.com/x")
    assert page.title == ""
    assert page.publish_date == ""
    assert links == []


@pytest.mark.parametrize(
    "text, want",
    [
        ("2025-03-14", "2025-03-14"),
        ("2025/3/4", "2025-03-04"),
        ("2025年3月14日", "2025-03-14"),
        ("2025.03.14", "2025-03-14"),
        ("发布时间：2019-12-01 10:30", "2019-12-01"),
        ("没有日期", ""),
        ("2025/13/40", ""),
    ],
)
def test_normalize_date(text, want):
    assert normalize_date(text) == want


def test_long_page_date_beyond_cap_is_ignored(parser):
    padding = "填充文字" * 1200          # 远超 3000 字的正文
    page, _ = parser.parse(f"<html><body><p>{padding}</p><p>2020-01-02</p></body></html>",
                           "http://a.com/x")
    assert page.publish_date == ""

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "CourseCrawler/1.0 (student project)"}
url = "https://www.python.org/"
r = requests.get(url, headers=UA, timeout=10)
r.encoding = r.apparent_encoding          # 关键：中文站点不设这行会乱码
soup = BeautifulSoup(r.text, "html.parser")

print("状态码:", r.status_code, "| 字节:", len(r.content))
print("标题:", soup.title.get_text(strip=True))
for a in soup.find_all("a", href=True)[:10]:
    print("  ", a.get_text(strip=True)[:20], "->", a["href"])

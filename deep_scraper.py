# deep_scraper.py  v2 — Two-layer architecture
# 替换旧版 BFS 爬虫
#
# 流程：
#   professors_index.json → 对每个教授
#     ├─ scrape_status ok/unknown → 两层抓 lab 网站
#     │    Layer 1: lab 主页（无条件存）
#     │    Layer 2: 主页链接 → 关键词过滤 → 抓子页（最多1层）
#     └─ 403 / js_rendered / no_lab_url → 直接 fallback 抓 faculty profile 页
#
# 输出：data/deep_scraped_professors.json（ingest.py 直接读取）

import json
import os
import re
import time
import warnings
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from urllib3.exceptions import InsecureRequestWarning

warnings.simplefilter("ignore", InsecureRequestWarning)

INDEX_FILE  = "data/professors_index.json"
OUTPUT_FILE = "data/deep_scraped_professors.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# 关键词：link text 或 URL path 中出现即视为目标页
TARGET_KEYWORDS = {
    "research": ["research", "project", "about"],
    "people":   ["people", "team", "member", "group"],
    "join":     ["join", "opening", "position", "prospective", "opportunit"],
    "teaching": ["teaching", "course", "class"],
}
SKIP_KEYWORDS = [
    "publication", "paper", "news", "video", "press",
    "gallery", "alumni", "calendar", "search", "blog", "tag",
]

MIN_CONTENT_CHARS = 200  # 内容低于此值视为无效页面


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def fetch_page(url, timeout=12):
    """HTTP GET，返回 Response 或 None（失败时打 log）"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout,
                            verify=False, allow_redirects=True)
        if resp.status_code == 200:
            return resp
        print(f"    [HTTP {resp.status_code}] {url}")
        return None
    except Exception as e:
        print(f"    [ERROR] {url} → {e}")
        return None


def is_js_rendered(resp):
    """内容极少 + 含 JS 框架特征 → 判定为 JS 渲染"""
    soup = BeautifulSoup(resp.content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    body_chars = len(soup.get_text(strip=True))
    if body_chars >= 500:
        return False
    js_signals = ["__NEXT_DATA__", "window.__NUXT__", "ng-app",
                  "data-reactroot", 'id="app"', 'id="root"']
    return any(sig in resp.text for sig in js_signals) or body_chars < 300


def clean_content(soup):
    """统一规则清洗：去噪声标签 → markdownify → 去图片行/导航行/重复行"""
    for tag in soup(["script", "style", "nav", "footer", "noscript", "header"]):
        tag.decompose()

    raw = md(str(soup), heading_style="ATX")

    seen = set()
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("!["):          # 纯图片行 ![alt](url)
            continue
        if re.match(r'^\[!\[', line):      # 图片包在链接里 [![alt](img)](url)
            continue
        if line.startswith("* [") or line.startswith("+ ["):  # 导航列表
            continue
        if line in seen:                   # 重复行
            continue
        seen.add(line)
        lines.append(line)

    return "\n".join(lines)


def get_domain(url):
    return urlparse(url).netloc


def normalize_url(url):
    """去掉 fragment（#section），避免同页被当成多个 URL"""
    defragged, _ = urldefrag(url)
    return defragged


# ── 链接过滤 ──────────────────────────────────────────────────────────────────

def path_depth(url):
    """URL path 的有效层数，如 /people/ → 1，/people/john → 2"""
    return len([s for s in urlparse(url).path.split("/") if s])


def filter_links(links, base_domain, homepage_url):
    """
    输入：[(url, link_text), ...]
    输出：[(url, page_type), ...] 仅保留同域名 + 关键词匹配 + 非 skip + 深度合理的链接

    深度限制：只接受比主页多 1 层 path 的链接，防止扎进个人主页等深层页面
    例：主页 = / (depth=0) → 只接受 /people/, /research/ (depth=1)
        主页 = /lab/ (depth=1) → 只接受 /lab/people/, /lab/research/ (depth=2)
    """
    max_depth = path_depth(homepage_url) + 1
    results = []
    seen_urls = set()

    for url, link_text in links:
        url = normalize_url(url)
        if url in seen_urls:
            continue

        # 必须同域名
        if get_domain(url) != base_domain:
            continue

        # 深度限制
        if path_depth(url) > max_depth:
            continue

        combined = (link_text + " " + url).lower()

        # 跳过噪声页（词边界匹配，避免 "search" 误伤 "research"）
        if any(re.search(r'\b' + k + r'\b', combined) for k in SKIP_KEYWORDS):
            continue

        # 匹配页面类型（子字符串匹配，关键词设计上不存在歧义）
        for page_type, keywords in TARGET_KEYWORDS.items():
            if any(k in combined for k in keywords):
                results.append((url, page_type))
                seen_urls.add(url)
                break

    return results


def extract_links(resp, base_url):
    """从页面提取所有 <a href>，返回 [(absolute_url, link_text), ...]"""
    soup = BeautifulSoup(resp.content, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = normalize_url(urljoin(base_url, a["href"]))
        text = a.get_text(strip=True).lower()
        if href.startswith("http"):
            links.append((href, text))
    return links


# ── 核心抓取逻辑 ──────────────────────────────────────────────────────────────

def scrape_page(url, page_type):
    """抓单个页面，清洗，返回 page_dict 或 None"""
    resp = fetch_page(url)
    if not resp:
        return None

    soup = BeautifulSoup(resp.content, "html.parser")
    content = clean_content(soup)

    if len(content) < MIN_CONTENT_CHARS:
        print(f"    [SKIP] 内容过少 ({len(content)} chars): {url}")
        return None

    title = (soup.title.string or "").strip() if soup.title else url

    return {
        "url": url,
        "title": title,
        "page_type": page_type,
        "content": content,
    }


def scrape_lab_site(lab_url):
    """
    两层抓取：主页 + 过滤后的子页
    返回 (pages_list, error_reason_or_None)
    """
    print(f"  → 抓主页: {lab_url}")
    resp = fetch_page(lab_url)

    if not resp:
        return [], "fetch_failed"

    if is_js_rendered(resp):
        print(f"  [JS渲染] 内容为空，跳过")
        return [], "js_rendered"

    pages = []

    # 主页
    home_page = scrape_page(lab_url, page_type="home")
    if home_page:
        pages.append(home_page)

    # 子页链接过滤
    base_domain = get_domain(resp.url)  # 用最终落地域名（处理重定向）
    raw_links = extract_links(resp, resp.url)
    target_links = filter_links(raw_links, base_domain, homepage_url=resp.url)

    print(f"  → 找到 {len(target_links)} 个目标子页")

    for sub_url, page_type in target_links:
        print(f"    [{page_type}] {sub_url}")
        time.sleep(0.4)
        page = scrape_page(sub_url, page_type=page_type)
        if page:
            pages.append(page)

    return pages, None


def fallback_profile(profile_url):
    """降级：抓 faculty profile 页作为兜底内容"""
    print(f"  [FALLBACK] 抓 profile 页: {profile_url}")
    page = scrape_page(profile_url, page_type="profile_fallback")
    return [page] if page else []


# ── 主流程 ────────────────────────────────────────────────────────────────────

def scrape_one(prof):
    """处理单个教授，返回结果 dict"""
    name   = prof["name"]
    status = prof["scrape_status"]
    errors = []

    print(f"\n[{name}] status={status}")

    # 需要直接 fallback 的情况
    if status in ("js_rendered", "blocked_403", "no_lab_url") or not prof.get("lab_url"):
        pages = fallback_profile(prof["profile_url"])
        fallback_used = True
    else:
        pages, err = scrape_lab_site(prof["lab_url"])
        fallback_used = False

        # lab 抓到内容太少 → fallback 补充
        if len(pages) == 0 or (err and err != "js_rendered"):
            if err:
                errors.append(err)
            print(f"  [FALLBACK] lab 内容不足，用 profile 补充")
            pages = fallback_profile(prof["profile_url"])
            fallback_used = True

    print(f"  ✓ 共 {len(pages)} 页")

    return {
        "name":       name,
        "slug":       prof["slug"],
        "department": "Robotics",
        "lab_url":    prof.get("lab_url"),
        "scraped_pages": pages,
        "scrape_log": {
            "status":        status,
            "pages_scraped": len(pages),
            "fallback_used": fallback_used,
            "errors":        errors,
        },
    }


def scrape_all(slugs=None):
    """
    scrape_all()           → 爬全部 35 个教授
    scrape_all(["slug1"])  → 只爬指定教授（调试用）
    """
    with open(INDEX_FILE) as f:
        index = json.load(f)

    if slugs:
        index = [p for p in index if p["slug"] in slugs]

    results = []
    for i, prof in enumerate(index):
        result = scrape_one(prof)
        results.append(result)

        # 增量写入，每5个教授保存一次（防止中途崩溃丢数据）
        if (i + 1) % 5 == 0 or (i + 1) == len(index):
            with open(OUTPUT_FILE, "w") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\n  [保存] {i+1}/{len(index)} 已写入 {OUTPUT_FILE}")

        time.sleep(1)

    print(f"\n完成：共 {len(results)} 个教授，{sum(len(r['scraped_pages']) for r in results)} 页")
    return results


if __name__ == "__main__":
    # 10个lab，覆盖不同网站类型
    scrape_all(slugs=[
        "nima-fazeli",           # WordPress 自定义域名
        "dimitra-panagou",       # GitHub Pages
        "dmitry-berenson",       # umich子域名，单页网站
        "katie-skinner",         # umich子域名
        "robert-gregg",          # umich子域名
        "necmiye-ozay",          # EECS个人主页
        "lionel-robert",         # Google Sites
        "christoforos-mavrogiannis",  # 自定义域名
        "talia-moore",           # Squarespace
        "xiaoxiao-du",           # WordPress个人站
    ])

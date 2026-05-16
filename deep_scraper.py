# deep_scraper.py  v3 — Crawl4AI (Playwright) backend
#
# 流程：
#   professors_index.json → 对每个教授
#     ├─ scrape_status blocked_403 / no_lab_url → fallback 抓 faculty profile
#     └─ 其余（含原 js_rendered）→ Crawl4AI 两层抓 lab 网站
#          Layer 1: lab 主页
#          Layer 2: 主页链接 → 关键词过滤 → 抓子页（最多1层）
#
# 输出：data/deep_scraped_professors.json（ingest.py 直接读取）

import asyncio
import json
import re
from urllib.parse import urlparse, urldefrag

from crawl4ai import AsyncWebCrawler

INDEX_FILE  = "data/professors_index.json"
OUTPUT_FILE = "data/deep_scraped_professors.json"

CONTENT_CAPS = {
    "home":     6000,
    "research": 10000,
    # people / join / teaching 不截断
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

MIN_CONTENT_CHARS = 200


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def get_markdown(result):
    """兼容 Crawl4AI 新旧版 API：result.markdown 可能是字符串或对象"""
    md = result.markdown
    if isinstance(md, str):
        return md
    if hasattr(md, "raw_markdown"):
        return md.raw_markdown or ""
    return str(md) if md else ""


def clean_markdown(text):
    """规则清洗：去图片行 / 导航列表行 / 空表格行 / 重复行"""
    seen = set()
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("!["):                   # 纯图片行
            continue
        if re.match(r'^\[!\[', line):               # 图片包在链接里
            continue
        if line.startswith("* [") or line.startswith("+ ["):   # 导航列表
            continue
        if line == '|':                                # 单独竖线残留
            continue
        if re.match(r'^\|[\s|]+\|$', line):           # 空表格行 |   |
            continue
        if re.match(r'^\|[\s|-]+\|$', line):          # 表格分隔行 | --- |
            continue
        if re.match(r'^\|\s*!\[', line):               # 表格图片格 |  ![img](url)  |
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return "\n".join(lines)


def get_domain(url):
    return urlparse(url).netloc


def normalize_url(url):
    defragged, _ = urldefrag(url)
    return defragged


# ── 链接过滤 ──────────────────────────────────────────────────────────────────

def path_depth(url):
    return len([s for s in urlparse(url).path.split("/") if s])


def filter_links(links, base_domain, homepage_url):
    """
    输入：[(url, link_text), ...]
    输出：[(url, page_type), ...] 同域名 + 关键词匹配 + 非 skip + 深度合理
    """
    max_depth = path_depth(homepage_url) + 1
    results = []
    seen_urls = set()

    for url, link_text in links:
        url = normalize_url(url)
        if url in seen_urls:
            continue
        if get_domain(url) != base_domain:
            continue
        if path_depth(url) > max_depth:
            continue

        combined = (link_text + " " + url).lower()

        if any(re.search(r'\b' + k + r'\b', combined) for k in SKIP_KEYWORDS):
            continue

        for page_type, keywords in TARGET_KEYWORDS.items():
            if any(k in combined for k in keywords):
                results.append((url, page_type))
                seen_urls.add(url)
                break

    return results


# ── 核心抓取逻辑 ──────────────────────────────────────────────────────────────

async def scrape_page(crawler, url, page_type):
    """抓单个页面，清洗，返回 page_dict 或 None"""
    result = await crawler.arun(url=url)
    if not result.success:
        print(f"    [ERROR] {url}")
        return None

    content = clean_markdown(get_markdown(result))
    if len(content) < MIN_CONTENT_CHARS:
        print(f"    [SKIP] 内容过少 ({len(content)} chars): {url}")
        return None

    cap = CONTENT_CAPS.get(page_type)
    if cap and len(content) > cap:
        content = content[:cap]
        print(f"    [CAP] {page_type} 截断至 {cap} chars: {url}")

    title = (result.metadata or {}).get("title", url)

    return {
        "url": url,
        "title": title,
        "page_type": page_type,
        "content": content,
    }


async def scrape_lab_site(crawler, lab_url):
    """两层抓取：主页 + 过滤后的子页"""
    print(f"  → 抓主页: {lab_url}")
    result = await crawler.arun(url=lab_url)

    if not result.success:
        return [], "fetch_failed"

    pages = []

    # 主页
    content = clean_markdown(get_markdown(result))
    cap = CONTENT_CAPS.get("home")
    if cap and len(content) > cap:
        content = content[:cap]
        print(f"    [CAP] home 截断至 {cap} chars: {lab_url}")
    if len(content) >= MIN_CONTENT_CHARS:
        title = (result.metadata or {}).get("title", lab_url)
        pages.append({
            "url": result.url,
            "title": title,
            "page_type": "home",
            "content": content,
        })

    # 子页链接过滤
    base_domain = get_domain(result.url)
    raw_links = [
        (normalize_url(l["href"]), l.get("text", ""))
        for l in result.links.get("internal", [])
        if l.get("href", "").startswith("http")
    ]
    homepage_url = normalize_url(result.url)
    target_links = filter_links(raw_links, base_domain, homepage_url=result.url)
    target_links = [(u, t) for u, t in target_links if normalize_url(u) != homepage_url]

    print(f"  → 找到 {len(target_links)} 个目标子页")

    for sub_url, page_type in target_links:
        print(f"    [{page_type}] {sub_url}")
        await asyncio.sleep(0.4)
        page = await scrape_page(crawler, sub_url, page_type=page_type)
        if page:
            pages.append(page)

    return pages, None


async def fallback_profile(crawler, profile_url):
    """降级：抓 faculty profile 页作为兜底内容"""
    print(f"  [FALLBACK] 抓 profile 页: {profile_url}")
    page = await scrape_page(crawler, profile_url, page_type="profile_fallback")
    return [page] if page else []


# ── 主流程 ────────────────────────────────────────────────────────────────────

async def scrape_one(crawler, prof):
    """处理单个教授，返回结果 dict"""
    name   = prof["name"]
    status = prof["scrape_status"]
    errors = []

    print(f"\n[{name}] status={status}")

    # blocked_403 / no_lab_url → 直接 fallback（Crawl4AI 也绕不过去）
    # js_rendered 现在由 Crawl4AI 处理，不再直接 fallback
    if status in ("blocked_403", "no_lab_url") or not prof.get("lab_url"):
        pages = await fallback_profile(crawler, prof["profile_url"])
        fallback_used = True
    else:
        pages, err = await scrape_lab_site(crawler, prof["lab_url"])
        fallback_used = False

        if len(pages) == 0:
            if err:
                errors.append(err)
            print(f"  [FALLBACK] lab 内容不足，用 profile 补充")
            pages = await fallback_profile(crawler, prof["profile_url"])
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


async def scrape_all(slugs=None, checkpoint_prefix=None):
    """
    scrape_all()           → 爬全部教授
    scrape_all(["slug1"])  → 只爬指定教授（调试用）
    checkpoint_prefix      → 中途保存时的前缀数据（不覆盖已有数据）
    """
    with open(INDEX_FILE) as f:
        index = json.load(f)

    if slugs:
        index = [p for p in index if p["slug"] in slugs]

    results = []
    async with AsyncWebCrawler() as crawler:
        for i, prof in enumerate(index):
            result = await scrape_one(crawler, prof)
            results.append(result)

            if (i + 1) % 5 == 0 or (i + 1) == len(index):
                save_data = (checkpoint_prefix or []) + results
                with open(OUTPUT_FILE, "w") as f:
                    json.dump(save_data, f, indent=2, ensure_ascii=False)
                print(f"\n  [保存] {i+1}/{len(index)} 已写入 {OUTPUT_FILE}（共 {len(save_data)} 个教授）")

            await asyncio.sleep(1)

    print(f"\n完成：共 {len(results)} 个教授，{sum(len(r['scraped_pages']) for r in results)} 页")
    return results


if __name__ == "__main__":
    import os

    # 加载已有数据，找出还没爬的
    existing = []
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            existing = json.load(f)

    scraped_slugs = {p["slug"] for p in existing}

    with open(INDEX_FILE) as f:
        index = json.load(f)
    remaining_slugs = [p["slug"] for p in index if p["slug"] not in scraped_slugs]

    if not remaining_slugs:
        print("所有教授已爬完。")
    else:
        print(f"剩余 {len(remaining_slugs)} 个教授待爬：{remaining_slugs}")

        async def run():
            await scrape_all(slugs=remaining_slugs, checkpoint_prefix=existing)
            print(f"\n合并完成，结果已实时保存至 {OUTPUT_FILE}")

        asyncio.run(run())

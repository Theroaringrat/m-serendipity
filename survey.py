"""
UMich Robotics 35位教授 lab网站摸底
检测：lab_url来源、JS渲染、403、iframe、内容量
"""

import requests
import warnings
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib3.exceptions import InsecureRequestWarning

warnings.simplefilter("ignore", InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

BASE = "https://robotics.umich.edu"

FACULTY_SLUGS = [
    "patricia-alves-oliveira", "cameron-aubin", "kira-barton",
    "dmitry-berenson", "bernadette-bucher", "steven-ceron",
    "cynthia-chestek", "jason-corso", "yanran-ding", "mark-draelos",
    "xiaoxiao-du", "nima-fazeli", "greg-formosa", "peter-gaskell",
    "deanna-gates", "maani-ghaffari", "brent-gillespie", "robert-gregg",
    "jessy-grizzle", "xiaonan-sean-huang", "chad-jenkins", "tribhi-kathuria",
    "christoforos-mavrogiannis", "talia-moore", "necmiye-ozay",
    "dimitra-panagou", "lionel-robert", "elliott-rouse", "katie-skinner",
    "leia-stirling", "yulun-tian", "dawn-tilbury", "ram-vasudevan",
    "xi-jessie-yang", "derrick-yeo",
]


def fetch(url, timeout=10):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
        return resp
    except Exception as e:
        return None


def detect_issues(resp, url):
    """返回 (body_chars, issues_list, lab_url_in_page)"""
    issues = []

    if resp is None:
        return 0, ["connection_error"], None
    if resp.status_code == 403:
        return 0, ["403_blocked"], None
    if resp.status_code == 404:
        return 0, ["404_not_found"], None
    if resp.status_code != 200:
        return 0, [f"http_{resp.status_code}"], None

    # 检查最终落地URL（判断重定向到登录墙）
    final_url = resp.url
    if "login" in final_url or "signin" in final_url:
        return 0, ["redirected_to_login"], None

    soup = BeautifulSoup(resp.content, "html.parser")

    # 提取lab链接（用于第二步）
    lab_url = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True).lower()
        if any(k in text for k in ["lab", "group", "website", "research group"]):
            full = urljoin(url, href)
            if "robotics.umich.edu" not in full and "umich.edu" in full or "://" in href:
                lab_url = full
                break
    # 备选：找所有外链里最可能是lab的
    if not lab_url:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("http") and "robotics.umich.edu" not in href and "umich.edu" not in href:
                text = a.get_text(strip=True).lower()
                if any(k in text for k in ["lab", "research", "group", "website"]):
                    lab_url = href
                    break

    # 去掉script/style/nav/footer
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()

    body_text = soup.get_text(separator=" ", strip=True)
    body_chars = len(body_text)

    # JS渲染检测：内容极少 + 原始HTML里有JS框架特征
    raw_html = resp.text
    js_signals = ["__NEXT_DATA__", "window.__NUXT__", "ng-app", "data-reactroot",
                  "id=\"app\"", "id=\"root\"", "ember-application"]
    is_js_rendered = body_chars < 500 and any(sig in raw_html for sig in js_signals)
    if body_chars < 300:
        is_js_rendered = True  # 内容太少，几乎肯定是JS渲染或空页

    if is_js_rendered:
        issues.append("js_rendered")

    # iframe检测
    iframes = soup.find_all("iframe")
    if iframes:
        issues.append(f"has_iframe({len(iframes)})")

    # 内容量评级
    if body_chars < 300:
        issues.append("content_empty")
    elif body_chars < 1000:
        issues.append("content_thin")

    return body_chars, issues, lab_url


def survey_professor(slug):
    profile_url = f"{BASE}/people/faculty/{slug}/"
    print(f"\n[{slug}]")

    # 第一步：抓 faculty profile 页，找 lab URL
    resp = fetch(profile_url)
    profile_chars, profile_issues, lab_url_from_profile = detect_issues(resp, profile_url)
    print(f"  profile: {profile_chars} chars  issues={profile_issues}  lab_url={lab_url_from_profile}")

    # 第二步：抓 lab 主页
    lab_result = None
    if lab_url_from_profile:
        time.sleep(0.5)
        lab_resp = fetch(lab_url_from_profile)
        lab_chars, lab_issues, _ = detect_issues(lab_resp, lab_url_from_profile)
        final_url = lab_resp.url if lab_resp else lab_url_from_profile

        # 判断lab网站类型
        domain = urlparse(final_url).netloc
        if "umich.edu" in domain:
            site_type = "umich_subdomain"
        elif "github.io" in domain:
            site_type = "github_pages"
        elif lab_resp and ("squarespace" in lab_resp.text[:2000].lower() or
                           "<!-- this is squarespace" in lab_resp.text[:2000].lower()):
            site_type = "squarespace"
        elif lab_resp and "wp-content" in lab_resp.text[:5000]:
            site_type = "wordpress"
        else:
            site_type = "custom"

        lab_result = {
            "url": lab_url_from_profile,
            "final_url": final_url,
            "site_type": site_type,
            "chars": lab_chars,
            "issues": lab_issues,
        }
        print(f"  lab:     {lab_chars} chars  type={site_type}  issues={lab_issues}")
        print(f"           url={lab_url_from_profile}")
    else:
        print(f"  lab:     no lab URL found on profile page")

    return {
        "slug": slug,
        "profile_url": profile_url,
        "profile_chars": profile_chars,
        "profile_issues": profile_issues,
        "lab": lab_result,
    }


if __name__ == "__main__":
    results = []
    for slug in FACULTY_SLUGS:
        result = survey_professor(slug)
        results.append(result)
        time.sleep(0.8)

    # 保存原始结果
    with open("data/survey_results.json", "w") as f:
        json.dump(results, f, indent=2)

    # 打印汇总
    print("\n" + "="*70)
    print("摸底汇总")
    print("="*70)

    js_rendered = [r for r in results if r["lab"] and "js_rendered" in r["lab"]["issues"]]
    blocked = [r for r in results if r["lab"] and any("403" in i or "connection" in i for i in r["lab"]["issues"])]
    no_lab_url = [r for r in results if not r["lab"]]
    thin = [r for r in results if r["lab"] and "content_thin" in r["lab"]["issues"] and "js_rendered" not in r["lab"]["issues"]]
    ok = [r for r in results if r["lab"] and not r["lab"]["issues"]]

    print(f"\n正常可抓取:       {len(ok)}/{len(results)}")
    print(f"JS渲染(抓不到):   {len(js_rendered)}/{len(results)}")
    print(f"找不到lab URL:    {len(no_lab_url)}/{len(results)}")
    print(f"403/连接失败:     {len(blocked)}/{len(results)}")
    print(f"内容偏少(可疑):   {len(thin)}/{len(results)}")

    print("\n--- JS渲染列表 ---")
    for r in js_rendered:
        print(f"  {r['slug']}: {r['lab']['url']}")

    print("\n--- 找不到lab URL ---")
    for r in no_lab_url:
        print(f"  {r['slug']}")

    print("\n--- 网站类型分布 ---")
    from collections import Counter
    types = Counter(r["lab"]["site_type"] for r in results if r["lab"])
    for t, count in types.most_common():
        print(f"  {t}: {count}")

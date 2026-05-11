"""
Branch A vs Branch B 爬虫方案对比实验
A: requests + markdownify（原文入库）
B: requests + markdownify + LLM 过滤（LLM转述入库）
"""

import os
import requests
import warnings
from urllib3.exceptions import InsecureRequestWarning
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

warnings.simplefilter("ignore", InsecureRequestWarning)

if "GOOGLE_API_KEY" not in os.environ:
    raise RuntimeError("Set GOOGLE_API_KEY environment variable before running")
llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TEST_URLS = [
    ("MMint Lab - Research", "https://www.mmintlab.com/research/"),
]


def fetch_branch_a(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
    soup = BeautifulSoup(resp.content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    raw_md = md(str(soup), heading_style="ATX")
    lines = [l.strip() for l in raw_md.splitlines() if l.strip()]
    return "\n".join(lines)


def fetch_branch_b(url: str, branch_a_text: str) -> str:
    prompt = f"""You are a text extractor for a RAG knowledge base about university research labs.

Extract ALL relevant content verbatim from the page below.
Include: research descriptions, project names, member names and roles, join/opening info, lab overview.
Exclude: navigation menus, footer links, cookie notices, image captions, social media buttons, repeated boilerplate headers.
DO NOT summarize. DO NOT paraphrase. Copy the relevant text exactly as it appears.

PAGE CONTENT:
{branch_a_text[:6000]}

OUTPUT: Only the extracted relevant text, preserving original wording."""

    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content
    if isinstance(content, list):
        content = " ".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return content


def clean_a(text: str) -> str:
    """规则清洗：去掉图片行、重复导航、空行压缩"""
    lines = text.splitlines()
    seen = set()
    cleaned = []
    for line in lines:
        # 去图片行
        if line.startswith("!["):
            continue
        # 去纯链接行（导航栏残留）
        if line.startswith("* [") or line.startswith("+ ["):
            continue
        # 去重复行
        if line in seen:
            continue
        seen.add(line)
        cleaned.append(line)
    return "\n".join(cleaned)


def analyze(label: str, url: str, text_a: str, text_b: str):
    text_a_clean = clean_a(text_a)

    print(f"\n{'='*70}")
    print(f"PAGE: {label} | URL: {url}")
    print(f"{'='*70}")
    print(f"A原始:   {len(text_a):>6} chars  {len(text_a.splitlines()):>4} lines")
    print(f"A清洗后: {len(text_a_clean):>6} chars  {len(text_a_clean.splitlines()):>4} lines")
    print(f"B输出:   {len(text_b):>6} chars  {len(text_b.splitlines()):>4} lines")

    # 保存完整输出到文件
    slug = label.replace(" ", "_").replace("-", "").replace("/", "")
    with open(f"experiment_{slug}_A_raw.txt", "w") as f:
        f.write(text_a)
    with open(f"experiment_{slug}_A_clean.txt", "w") as f:
        f.write(text_a_clean)
    with open(f"experiment_{slug}_B.txt", "w") as f:
        f.write(text_b)
    print(f"\n完整输出已保存到 experiment_{slug}_*.txt")


if __name__ == "__main__":
    for label, url in TEST_URLS:
        try:
            print(f"\nFetching: {url}")
            text_a = fetch_branch_a(url)
            text_b = fetch_branch_b(url, text_a)
            analyze(label, url, text_a, text_b)
        except Exception as e:
            print(f"[ERROR] {label}: {e}")

# M-Serendipity 项目计划
**最后更新：2026-05-12**

---

## 项目定位

帮学生判断"这个 Lab 值不值得联系"，回答三个核心问题：
1. 研究方向和我的兴趣匹不匹配？
2. 这个 Lab 带不带本科生？
3. 有没有机会进去？

**技术定位**：面向暑假实习申请的核心 portfolio 项目，覆盖完整 RAG + Agent 链路。

---

## JD 技能图谱

| JD 要求 | 状态 | 覆盖阶段 |
|---------|------|---------|
| RAG（LangChain、ChromaDB、Embedding） | ✅ | Phase 1 |
| 结构化输出（Pydantic） | ✅ | 已有 |
| Agent（Tool calling、ReAct） | ❌ | Phase 2 |
| 多轮对话 + 记忆 | ❌ | Phase 2 |
| 工程基础（数据管道） | 🟡 | Phase 1 完善 |
| LangGraph | ❌ | Phase 3（可选） |

---

## Phase 1：数据层

**目标**：35 位教授的 lab 数据进 vector_db，质量撑得起简历描述。

**爬虫方案**：两层架构（professors_index.json → lab 主页 → 子页，最多1层）
- 爬取目标：research / people / join / teaching 四类页面
- 清洗：rules-based（去导航/图片/重复行）
- 降级：403 / JS渲染 / 无lab URL → fallback 到 faculty profile 页

**各页面目标信息**：

| page_type | 回答的问题 | 有效字符目标 |
|-----------|-----------|------------|
| research | 研究方向匹不匹配？ | 1000-5000 chars |
| people | 带不带本科生？ | 500-1500 chars |
| join | 有没有机会进去？ | 200-800 chars |
| teaching | 辅助了解教授方向 | 200-1000 chars |
| home | 总体定位兜底 | 500-2000 chars |

**工程完善**：ingest.py 加 page_type metadata、backend.py 加 logging、数据质量检查

**简历描述**：Built a RAG pipeline covering 35+ professors using LangChain + ChromaDB + Gemini Embedding

---

## Phase 2：Agent 能力

**目标**：从单步 RAG 升级为有工具调用和记忆的 Agent。

- **2a. Tool Calling**：search_professors / get_professor_by_name / get_recent_publications
- **2b. ReAct Agent**：用 `create_react_agent` 替换现有 `prompt | structured_llm`
- **2c. 多轮记忆**：`st.session_state` + `ConversationBufferMemory`

Publications 策略：不预先 ingest，由 Agent 在学生追问时实时抓取最近5篇。

**简历描述**：Implemented a multi-tool ReAct agent with conversation memory for academic advisor use case

---

## Phase 3：架构升级（可选）

LangGraph 重写 Agent 流程。Phase 1 + 2 稳定后根据面试反馈决定。

---

## Ideas（有余力时）

- 核心论文概括（LLM 生成代表作摘要）
- 学生主页抓取（推断 lab 适合什么背景的人）
- 出版质量/频率评估（venue 档次作为 lab 活跃度信号）

---

## 执行顺序

```
Phase 1（爬虫 → ingest）→ Phase 2a（工具）→ Phase 2b（ReAct）→ Phase 2c（记忆）→ Phase 3（可选）
```

每一步都是可独立交付的节点。

---

---

# 工程日志

---

## 当前状态（2026-05-12）

- [x] 基础 RAG 管道（3 位教授，1674 chunks）
- [x] 结构化输出、Gemini Embedding、Streamlit 前端
- [x] 爬虫方案决策（Branch A：requests + markdownify + 规则清洗）
- [x] 全站摸底（35 位教授，survey.py）
- [x] professors_index.json 建立
- [x] deep_scraper.py 完整重写（两层架构）
- [x] 10 个 lab 验证，发现系统性噪声问题
- [ ] **待决策：是否换 Crawl4AI（解决表格噪声 + JS 渲染）**
- [ ] 跑全 35 个教授 + 重建 vector_db
- [ ] Phase 2

---

## 2026-05-12 爬虫重写记录

### 架构决策

- Branch B（LLM 过滤层）被否定：LLM 在 ingest 层破坏 RAG 原文可信性，且手写 verbatim 不可靠
- Branch A 确定：requests + markdownify + rules-based 清洗

### 35 lab 摸底结果

| 类别 | 数量 | 处理方式 |
|------|------|---------|
| 正常可抓 | ~20 | 两层架构直接跑 |
| 403 封锁 | 5 | fallback profile |
| JS 渲染 | 2（CURLY / ICRL）| fallback profile |
| 无 lab URL | 3 | fallback profile |

### 10 lab 测试发现的数据质量问题

| 问题 | 影响 lab | 严重程度 |
|------|---------|---------|
| HTML 布局表格 → 大量空 `\|  \|` 行 | Mavrogiannis、Ozay | 严重 |
| 同 URL 存两次（不同 page_type） | Ozay、Skinner | 中等 |
| 平台导航噪声（Google Sites / WordPress） | Robert、Du、Skinner | 中等 |
| JS 渲染子页（DASC projects 36 chars） | Panagou | 中等 |
| Alumni / Grants 段落（ARM 38K噪声） | Berenson、Robert | 严重 |

### 代码修复记录

- depth 限制（`path_depth(url) <= homepage_depth + 1`）→ 防止扎进个人主页
- `\bsearch\b` 词边界 → 防止误过滤 research 页
- `re.match(r'^\[!\[', line)` → 过滤 linked image（`[![](img)](url)`）
- `soup.title.string or ""` → 修复 title 为 None 时的 crash

### 待决策

Crawl4AI vs 继续手写规则：
- 表格噪声 + 平台导航 → Crawl4AI 的 PruningContentFilter 能系统性解决，手写规则是打地鼠
- 代价：WSL 装 Playwright + Chromium ~300MB，有崩溃风险
- 当前阻塞因素：不确定 WSL 能否稳定安装
